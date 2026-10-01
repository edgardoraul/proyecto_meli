import json
import logging
import sys
from pathlib import Path
import pandas as pd
import requests
from controllers.DescargaPrecios import DescargaPrecios

from config.settings import CUENTAS, DATA_DIR, MELI_API_URL
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

# Constantes de cálculo
COEF_PRE = 1.35
COEF_CLA = 1.25
COSTO_FIJO = 700

# Columnas del listado de precios
id = "Artículo"
precio_publico = "Precio"



def cargar_precios_csv() -> dict:
    archivo_csv = DATA_DIR / "PreciosDeArticulos.csv"
    if not archivo_csv.exists():
        logger.error(f"❌ No se encontró el archivo CSV en: {archivo_csv}")
        return {}

    try:
        df = pd.read_csv(archivo_csv)
        df.columns = df.columns.str.strip()

        if id not in df.columns or precio_publico not in df.columns:
            logger.error(
                f"❌ El CSV debe contener las columnas {id} y {precio_publico}."
            )
            return {}

        precios_map = {}
        for _, row in df.iterrows():
            item_id = str(row[id]).strip().upper()
            try:
                precio_base = float(row[precio_publico])
                precios_map[item_id] = precio_base
            except ValueError:
                continue

        logger.info(
            f"📊 Planilla CSV cargada: {len(precios_map)} precios base encontrados."
        )
        return precios_map
    except Exception as e:
        logger.error(f"❌ Error al leer la planilla CSV: {e}")
        return {}


def obtener_todas_publicaciones(headers: dict, user_id: int) -> list:
    ids = []
    offset = 0
    limit = 100
    url = f"{MELI_API_URL}/users/{user_id}/items/search"

    while True:
        params = {"status": "active", "limit": limit, "offset": offset}
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()

        results = data.get("results", [])
        if not results:
            break

        ids.extend(results)
        offset += len(results)

        if offset >= data.get("paging", {}).get("total", 0):
            break

    return ids


def obtener_detalles_lote(headers: dict, item_ids: list) -> list:
    detalles = []
    for i in range(0, len(item_ids), 20):
        chunk = item_ids[i : i + 20]
        ids_str = ",".join(chunk)
        url = f"{MELI_API_URL}/items?ids={ids_str}"

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                for item_data in res.json():
                    if item_data.get("code") == 200:
                        detalles.append(item_data.get("body", {}))
        except Exception as e:
            logger.warning(f"Error consultando lote de ítems: {e}")
    return detalles


def procesar_cuenta(cuenta_config: dict, mapa_precios: dict):
    logger.info(
        f"\n============================================================"
    )
    logger.info(f" 🚀 PROCESANDO CUENTA: {cuenta_config['nombre']}")
    logger.info(
        f"============================================================"
    )

    # 1. Autenticación con salto limpio si no existe el archivo de tokens
    try:
        auth = MeLiAuth(cuenta_config)
        token = auth.get_access_token()
    except FileNotFoundError:
        logger.warning(
            f"⚠️ Se omite la cuenta [{cuenta_config['nombre']}]: No existe el archivo de tokens '{cuenta_config['token_file'].name}'."
        )
        return
    except Exception as e:
        logger.error(
            f"❌ Error de autenticación en [{cuenta_config['nombre']}]: {e}"
        )
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Obtención de datos del usuario
    try:
        res = requests.get(
            f"{MELI_API_URL}/users/me", headers=headers, timeout=10
        )
        res.raise_for_status()
        user_id = res.json()["id"]
    except Exception as e:
        logger.error(
            f"❌ Error al obtener ID de usuario para [{cuenta_config['nombre']}]: {e}"
        )
        return

    logger.info("🔍 Obteniendo lista completa de publicaciones activas...")
    item_ids = obtener_todas_publicaciones(headers, user_id)
    logger.info(
        f"📦 Total de publicaciones activas encontradas: {len(item_ids)}"
    )

    logger.info("⚡ Descargando detalles de las publicaciones...")
    detalles = obtener_detalles_lote(headers, item_ids)

    # Guardar datos crudos descargados en JSON
    archivo_json = (
        DATA_DIR
        / f"publicaciones_{cuenta_config['nombre'].replace(' ', '_').lower()}.json"
    )

    data_export = {"total": len(detalles), "results": detalles}

    with open(archivo_json, "w", encoding="utf-8") as f:
        json.dump(data_export, f, indent=4, ensure_ascii=False)

    logger.info(f"✔ Archivo JSON guardado en: {archivo_json}")

"""
    # =========================================================================
    # INICIO DE COMENTARIO: Lógica de actualización deshabilitada para pruebas
    # =========================================================================

    for item in detalles:
        item_id = item.get("id")
        listing_type_id = item.get("listing_type_id")
        precio_actual = item.get("price", 0.0)

        if listing_type_id != "gold_pro" or item_id not in mapa_precios:
            continue

        precio_publico = mapa_precios[item_id]
        
        # Nueva fórmula con redondeo a enteros (0 decimales)
        precio_calculado = round(
            #(((precio_publico - COSTO_FIJO) / COEF_CLA) * COEF_PRE) + COSTO_FIJO, 0
            precio_publico * COEF_PRE + COSTO_FIJO, 0
        )

        logger.info(f"[{item_id}] Actual: ${precio_actual} -> Calculado: ${precio_calculado}")

    # =========================================================================
    # FIN DE COMENTARIO
    # =========================================================================
"""

def main():
    logger.info("🏁 Inicio de prueba de descarga de publicaciones")

    # 1. Descarga la lista de precios y genera/actualiza PreciosDeArticulos.XLS
    DescargaPrecios()

    # 2. Carga los precios del Excel generado
    mapa_precios = cargar_precios_csv()

    for key, cuenta_config in CUENTAS.items():
        try:
            procesar_cuenta(cuenta_config, mapa_precios)
        except Exception as e:
            logger.error(
                f"❌ Error procesando la cuenta {cuenta_config.get('nombre')}: {e}",
                exc_info=True,
            )

    logger.info("🎉 Proceso de prueba finalizado.\n")


if __name__ == "__main__":
    main()