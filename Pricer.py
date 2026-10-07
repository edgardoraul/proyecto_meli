# Archivo Pricer.py

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

from config.settings import CUENTAS, DATA_DIR, MELI_API_URL
from controllers.DescargaPrecios import DescargaPrecios
from controllers.PricerUpdater import actualizar_precios_cuenta
from models.auth import MeLiAuth

LOG_FILE = DATA_DIR / "pricer.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Pricer")


def extraer_sku_de_objeto(data: dict) -> str:
    """Busca el SKU en seller_custom_field, attributes y attribute_combinations."""
    if not isinstance(data, dict):
        return ""

    # 1. Campo legacy directo
    scf = data.get("seller_custom_field")
    if scf and str(scf).strip():
        return str(scf).strip().upper()

    # 2. Atributos estándar o combinaciones en variaciones (nuevo modelo MeLi)
    for list_key in ["attributes", "attribute_combinations"]:
        for attr in data.get(list_key, []):
            if not isinstance(attr, dict):
                continue
            attr_id = str(attr.get("id", "")).upper()
            attr_name = str(attr.get("name", "")).upper()

            if attr_id in ("SELLER_SKU", "SKU", "SELLER_CUSTOM_FIELD", "PART_NUMBER") or "SKU" in attr_id or "SKU" in attr_name:
                val_name = attr.get("value_name")
                if val_name and str(val_name).strip():
                    return str(val_name).strip().upper()

                values = attr.get("values", [])
                if isinstance(values, list) and len(values) > 0:
                    first_val = values[0]
                    if isinstance(first_val, dict):
                        v_name = first_val.get("name")
                        if v_name and str(v_name).strip():
                            return str(v_name).strip().upper()
    return ""


def extraer_sku_item_completo(item: dict) -> str:
    """Extrae el SKU del nivel raíz o de cualquiera de sus variaciones."""
    sku_root = extraer_sku_de_objeto(item)
    if sku_root:
        return sku_root

    for v in item.get("variations", []):
        sku_v = extraer_sku_de_objeto(v)
        if sku_v:
            return sku_v

    return ""


def obtener_item_individual(item_id: str, headers: dict) -> dict | None:
    """Consulta una publicación individual para obtener el JSON con atributos de variaciones completos."""
    try:
        res = requests.get(f"{MELI_API_URL}/items/{item_id}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.warning(f"Error re-consultando {item_id}: {e}")
    return None


def consultar_lote_items(chunk_ids: list, headers: dict) -> list:
    """Consulta masiva por lote (20 ítems)."""
    ids_str = ",".join(chunk_ids)
    url = f"{MELI_API_URL}/items?ids={ids_str}"
    items = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for item_data in res.json():
                if item_data.get("code") == 200:
                    body = item_data.get("body", {})
                    if body.get("listing_type_id") == "gold_pro":
                        items.append(body)
    except Exception as e:
        logger.warning(f"Error en consulta por lote: {e}")
    return items


def descargar_publicaciones_premium_rapido(headers: dict, user_id: int) -> list:
    """
    Descarga híbrida paralela:
    1. Descarga en lotes masivos (10 hilos).
    2. Identifica publicaciones sin SKU recortadas por MeLi.
    3. Re-consulta solo las incompletas en paralelo (20 hilos) para obtener sus variaciones.
    """
    logger.info("🔍 Obteniendo lista de IDs activos desde Mercado Libre...")
    item_ids = []
    offset = 0
    limit = 100
    url_search = f"{MELI_API_URL}/users/{user_id}/items/search"

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

    logger.info(f"📦 Total publicaciones activas: {len(item_ids)}. Procesando en lotes paralelos...")

    # 1. Consulta masiva inicial
    chunks = [item_ids[i : i + 20] for i in range(0, len(item_ids), 20)]
    items_premium_raw = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(consultar_lote_items, chunk, headers) for chunk in chunks]
        for future in as_completed(futures):
            items_premium_raw.extend(future.result())

    logger.info(f"⚡ {len(items_premium_raw)} publicaciones Premium encontradas. Verificando SKUs...")

    # 2. Identificar ítems recortados sin SKU
    items_incompletos_ids = [item.get("id") for item in items_premium_raw if not extraer_sku_item_completo(item)]

    # 3. Re-consulta individual paralela de ítems recortados
    items_reconsultados = {}
    if items_incompletos_ids:
        logger.info(f"🔄 Re-consultando {len(items_incompletos_ids)} publicaciones en paralelo para rescatar SKUs de variaciones...")
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_id = {executor.submit(obtener_item_individual, i_id, headers): i_id for i_id in items_incompletos_ids}
            for future in as_completed(future_to_id):
                res_item = future.result()
                if res_item:
                    items_reconsultados[res_item.get("id")] = res_item

    # 4. Inyección y normalización de SKUs
    publicaciones_finales = []
    for item in items_premium_raw:
        item_id = item.get("id")
        if item_id in items_reconsultados:
            item = items_reconsultados[item_id]

        sku_hallado = extraer_sku_item_completo(item)

        if sku_hallado:
            item["seller_custom_field"] = sku_hallado
            for v in item.get("variations", []):
                v_sku = extraer_sku_de_objeto(v) or sku_hallado
                v["seller_custom_field"] = v_sku

        publicaciones_finales.append(item)

    logger.info(f"✅ Descarga y rescate finalizado. {len(publicaciones_finales)} publicaciones listas.")
    return publicaciones_finales


def cargar_precios_csv() -> dict:
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
    logger.info("\n============================================================")
    logger.info(f" 🚀 PROCESANDO CUENTA: {cuenta_config['nombre']}")
    logger.info("============================================================")

    try:
        auth = MeLiAuth(cuenta_config)
        token = auth.get_access_token()
    except Exception as e:
        logger.error(f"❌ Error de autenticación en [{cuenta_config['nombre']}]: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    try:
        res = requests.get(f"{MELI_API_URL}/users/me", headers=headers, timeout=10)
        res.raise_for_status()
        user_id = res.json()["id"]
    except Exception as e:
        logger.error(f"❌ Error al obtener ID de usuario: {e}")
        return

    detalles = descargar_publicaciones_premium_rapido(headers, user_id)

    archivo_json = DATA_DIR / f"publicaciones_{cuenta_config['nombre'].replace(' ', '_').lower()}.json"
    with open(archivo_json, "w", encoding="utf-8") as f:
        json.dump({"total": len(detalles), "results": detalles}, f, indent=4, ensure_ascii=False)

    logger.info(f"✔ JSON guardado ({len(detalles)} Premium) en: {archivo_json.name}")
    logger.info("🔄 Iniciando actualización de precios...")
    actualizar_precios_cuenta(cuenta_config, detalles, mapa_precios, headers)


def main():
    logger.info("🏁 INICIO DE PROCESO GENERAL DE PRECIOS")
    DescargaPrecios()
    mapa_precios = cargar_precios_csv()

    for key, cuenta_config in CUENTAS.items():
        try:
            procesar_cuenta(cuenta_config, mapa_precios)
        except Exception as e:
            logger.error(f"❌ Error en cuenta {cuenta_config.get('nombre')}: {e}")

    logger.info("🎉 PROCESO FINALIZADO.\n")


if __name__ == "__main__":
    main()