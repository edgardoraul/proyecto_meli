# ==============================================================================
# ARCHIVO: Pricer.py
# DESCRIPCIÓN: Script principal coordinador para la sincronización automática
#              de precios en Mercado Libre (cuentas Premium / gold_pro) a partir
#              de la lista de precios de Dragonfish (PreciosDeArticulos.csv).
# ==============================================================================

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

# Importación de configuraciones, autenticación y controladores secundarios
from config.settings import CUENTAS, DATA_DIR, MELI_API_URL
from controllers.DescargaPrecios import DescargaPrecios
from controllers.PricerUpdater import actualizar_precios_cuenta
from models.auth import MeLiAuth

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DEL SISTEMA DE LOGS (Registro de eventos)
# ------------------------------------------------------------------------------
LOG_FILE = DATA_DIR / "pricer.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"), # Guarda eventos en disco
        logging.StreamHandler(sys.stdout),              # Muestra eventos en consola
    ],
)
logger = logging.getLogger("Pricer")


# ==============================================================================
# FUNCIONES AUXILIARES DE EXTRACCIÓN DE SKUs
# ==============================================================================

def extraer_sku_directo(data: dict) -> str:
    """
    Busca el código SKU cargado directamente dentro del JSON de un ítem o variante.
    
    Estrategia de búsqueda:
    1. Revisa el campo legacy 'seller_custom_field'.
    2. Recorre las listas de atributos ('attributes' y 'attribute_combinations')
       buscando etiquetas como 'SELLER_SKU', 'SKU' o 'SELLER_CUSTOM_FIELD'.
    """
    if not isinstance(data, dict):
        return ""

    # 1. Búsqueda en campo legacy directo
    scf = data.get("seller_custom_field")
    if scf and str(scf).strip():
        return str(scf).strip().upper()

    # 2. Búsqueda en listas de atributos de Mercado Libre
    for list_key in ["attributes", "attribute_combinations"]:
        for attr in data.get(list_key, []):
            if not isinstance(attr, dict):
                continue
            attr_id = str(attr.get("id", "")).upper()
            if attr_id in ("SELLER_SKU", "SKU", "SELLER_CUSTOM_FIELD"):
                # Intenta extraer de 'value_name'
                v_name = attr.get("value_name")
                if v_name and str(v_name).strip():
                    return str(v_name).strip().upper()
                
                # O del primer elemento en la lista 'values'
                values = attr.get("values", [])
                if isinstance(values, list) and len(values) > 0 and isinstance(values[0], dict):
                    name = values[0].get("name")
                    if name and str(name).strip():
                        return str(name).strip().upper()
    return ""


def obtener_sku_user_product(user_product_id: str, headers: dict) -> str:
    """
    Mecanismo de Rescate (Fallback) para publicaciones de Catálogo / User Products:
    Cuando Mercado Libre oculta el SKU del ítem principal, se consulta directamente
    el endpoint '/user-products/{user_product_id}' donde está almacenado.
    
    Incluye 2 intentos y timeout de 15s para evitar cuelgues por saturación de red.
    """
    url = f"{MELI_API_URL}/user-products/{user_product_id}"
    
    for intento in range(2):
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                
                # 1. Probar campo de raíz
                scf = data.get("seller_custom_field") or data.get("sku")
                if scf and str(scf).strip():
                    return str(scf).strip().upper()

                # 2. Probar dentro del listado de atributos del User Product
                for attr in data.get("attributes", []):
                    if not isinstance(attr, dict):
                        continue
                    attr_id = str(attr.get("id", "")).upper()
                    if attr_id in ("SELLER_SKU", "SKU", "SELLER_CUSTOM_FIELD"):
                        v_name = attr.get("value_name")
                        if v_name and str(v_name).strip():
                            return str(v_name).strip().upper()
                        values = attr.get("values", [])
                        if isinstance(values, list) and len(values) > 0 and isinstance(values[0], dict):
                            name = values[0].get("name")
                            if name and str(name).strip():
                                return str(name).strip().upper()
                return ""
        except requests.exceptions.RequestException:
            if intento == 1:
                logger.warning(f"Timeout definitivo consultando user-product {user_product_id}")
    return ""


# ==============================================================================
# FUNCIONES DE DESCARGA MASIVA Y PARALELA DE PUBLICACIONES
# ==============================================================================

def consultar_lote_items(chunk_ids: list, headers: dict) -> list:
    """
    Consulta un lote de hasta 20 IDs mediante el endpoint multiget (/items?ids=...).
    Filtra y conserva únicamente aquellas publicaciones de tipo 'gold_pro' (Premium).
    """
    ids_str = ",".join(chunk_ids)
    url = f"{MELI_API_URL}/items?ids={ids_str}"
    items = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for item_data in res.json():
                if item_data.get("code") == 200:
                    body = item_data.get("body", {})
                    # Solo se aceptan publicaciones Premium
                    if body.get("listing_type_id") == "gold_pro":
                        items.append(body)
    except Exception as e:
        logger.warning(f"Error consultando lote de ítems: {e}")
    return items


def descargar_publicaciones_premium_rapido(headers: dict, user_id: int) -> list:
    """
    FLUJO PRINCIPAL DE DESCARGA E INYECCIÓN HÍBRIDA DE SKUs:
    
    Paso 1: Obtiene la lista completa de IDs de publicaciones activas.
    Paso 2: Descarga los detalles en lotes paralelos de 20 (usando 10 hilos).
    Paso 3: Identifica ítems/variantes con SKU omitido y junta sus 'user_product_id'.
    Paso 4: Consulta en paralelo los User Products (máx 8 hilos) para rescatar los SKUs.
    Paso 5: Normaliza e inyecta el SKU resuelto en 'seller_custom_field' para su fácil lectura.
    """
    logger.info("🔍 Obteniendo IDs activos desde Mercado Libre...")
    item_ids = []
    offset = 0
    limit = 100
    url_search = f"{MELI_API_URL}/users/{user_id}/items/search"

    # Paginación para obtener la totalidad de IDs activos del usuario
    while True:
        params = {"status": "active", "limit": limit, "offset": offset}
        res = requests.get(url_search, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])
        if not results:
            break
        item_ids.extend(results)
        offset += len(results)
        if offset >= data.get("paging", {}).get("total", 0):
            break

    logger.info(f"📦 Total de publicaciones activas: {len(item_ids)}. Descargando por lotes...")

    # PASO 2: División en lotes de 20 y ejecución en hilos paralelos
    chunks = [item_ids[i : i + 20] for i in range(0, len(item_ids), 20)]
    items_premium_raw = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(consultar_lote_items, chunk, headers) for chunk in chunks]
        for future in as_completed(futures):
            items_premium_raw.extend(future.result())

    logger.info(f"⚡ {len(items_premium_raw)} publicaciones Premium encontradas. Verificando SKUs y User Products...")

    # PASO 3: Detección de variaciones/ítems que necesitan rescate vía /user-products
    user_products_a_consultar = set()

    for item in items_premium_raw:
        variaciones = item.get("variations", [])
        if variaciones:
            for v in variaciones:
                sku = extraer_sku_directo(v)
                if not sku and v.get("user_product_id"):
                    user_products_a_consultar.add(v["user_product_id"])
        else:
            sku = extraer_sku_directo(item)
            if not sku and item.get("user_product_id"):
                user_products_a_consultar.add(item["user_product_id"])

    # PASO 4: Consulta concurrente controlada (8 hilos) a la API de User Products
    mapa_user_products = {}
    if user_products_a_consultar:
        logger.info(f"🔄 Consultando {len(user_products_a_consultar)} User Products en paralelo para extraer SKUs...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_up = {
                executor.submit(obtener_sku_user_product, up_id, headers): up_id
                for up_id in user_products_a_consultar
            }
            for future in as_completed(future_to_up):
                up_id = future_to_up[future]
                sku_hallado = future.result()
                if sku_hallado:
                    mapa_user_products[up_id] = sku_hallado

    # PASO 5: Asignación e inyección final del SKU en la clave 'seller_custom_field'
    for item in items_premium_raw:
        variaciones = item.get("variations", [])
        sku_raiz_candidato = ""

        if variaciones:
            for v in variaciones:
                sku_v = extraer_sku_directo(v)
                if not sku_v and v.get("user_product_id"):
                    sku_v = mapa_user_products.get(v["user_product_id"], "")

                if sku_v:
                    v["seller_custom_field"] = sku_v
                    if not sku_raiz_candidato:
                        sku_raiz_candidato = sku_v

            item["seller_custom_field"] = extraer_sku_directo(item) or sku_raiz_candidato
        else:
            sku_item = extraer_sku_directo(item)
            if not sku_item and item.get("user_product_id"):
                sku_item = mapa_user_products.get(item["user_product_id"], "")

            if sku_item:
                item["seller_custom_field"] = sku_item

    logger.info("✅ Extracción de SKUs finalizada con éxito.")
    return items_premium_raw


# ==============================================================================
# CARGA Y PROCESAMIENTO DE PLANILLA CSV Y CUENTAS
# ==============================================================================

def cargar_precios_csv() -> dict:
    """
    Lee el archivo 'PreciosDeArticulos.csv' generado desde Dragonfish.
    Retorna un diccionario de mapeo rápido: { "CODIGO_ARTICULO": PRECIO_FLOAT }.
    """
    archivo_csv = DATA_DIR / "PreciosDeArticulos.csv"
    if not archivo_csv.exists():
        logger.error(f"❌ No se encontró el archivo CSV en: {archivo_csv}")
        return {}
    try:
        df = pd.read_csv(archivo_csv)
        df.columns = df.columns.str.strip()
        precios_map = {}
        for _, row in df.iterrows():
            art = str(row["Articulo"]).strip().upper()
            try:
                precios_map[art] = float(row["Precio"])
            except ValueError:
                continue
        logger.info(f"📊 Planilla CSV cargada: {len(precios_map)} artículos base.")
        return precios_map
    except Exception as e:
        logger.error(f"❌ Error al leer la planilla CSV: {e}")
        return {}


def procesar_cuenta(cuenta_config: dict, mapa_precios: dict):
    """
    Procesa una cuenta individual configurada en settings.py:
    1. Autentica y obtiene Access Token.
    2. Obtiene ID del usuario en Mercado Libre.
    3. Descarga publicaciones Premium con SKUs 100% resueltos.
    4. Guarda respaldo local en archivo JSON.
    5. Llama a 'PricerUpdater' para efectuar el cálculo y PUT de precios.
    """
    logger.info("\n============================================================")
    logger.info(f" 🚀 PROCESANDO CUENTA: {cuenta_config['nombre']}")
    logger.info("============================================================")

    # 1. Autenticación
    try:
        auth = MeLiAuth(cuenta_config)
        token = auth.get_access_token()
    except Exception as e:
        logger.error(f"❌ Error de autenticación en [{cuenta_config['nombre']}]: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Obtención de datos de usuario
    try:
        res = requests.get(f"{MELI_API_URL}/users/me", headers=headers, timeout=10)
        res.raise_for_status()
        user_id = res.json()["id"]
    except Exception as e:
        logger.error(f"❌ Error al obtener ID de usuario: {e}")
        return

    # 3. Descarga optimizada de publicaciones
    detalles = descargar_publicaciones_premium_rapido(headers, user_id)

    # 4. Guardado de JSON crudo/estructurado
    archivo_json = DATA_DIR / f"publicaciones_{cuenta_config['nombre'].replace(' ', '_').lower()}.json"
    with open(archivo_json, "w", encoding="utf-8") as f:
        json.dump({"total": len(detalles), "results": detalles}, f, indent=4, ensure_ascii=False)

    logger.info(f"✔ JSON guardado ({len(detalles)} Premium) en: {archivo_json.name}")
    
    # 5. Ejecución del proceso de actualización de precios en Mercado Libre
    logger.info("🔄 Iniciando actualización de precios...")
    actualizar_precios_cuenta(cuenta_config, detalles, mapa_precios, headers)


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL (MAIN)
# ==============================================================================

def main():
    """
    Función orquestadora principal:
    1. Descarga/Actualiza catálogo PUB desde Dragonfish (DescargaPrecios).
    2. Carga en memoria el mapa de precios base del CSV.
    3. Iterar y procesar cada cuenta de Mercado Libre configurada.
    """
    logger.info("🏁 INICIO DE PROCESO GENERAL DE PRECIOS")
    
    # Descarga la planilla de precios actualizada
    DescargaPrecios()
    
    # Carga precios en memoria
    mapa_precios = cargar_precios_csv()

    # Procesa cada cuenta configurada (Principal, Secundaria, etc.)
    for key, cuenta_config in CUENTAS.items():
        try:
            procesar_cuenta(cuenta_config, mapa_precios)
        except Exception as e:
            logger.error(f"❌ Error en cuenta {cuenta_config.get('nombre')}: {e}")

    logger.info("🎉 PROCESO FINALIZADO.\n")


if __name__ == "__main__":
    main()