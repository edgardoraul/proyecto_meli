import json
import logging
import pandas as pd
import requests

from config.settings import DATA_DIR, PRICER_API_URL

logger = logging.getLogger("Pricer")


def DescargaPrecios() -> bool:
    archivo_token = DATA_DIR / "token_pricer_meli.json"

    if not archivo_token.exists():
        logger.error(f"❌ No existe el archivo de token en: {archivo_token}")
        return False

    try:
        with open(archivo_token, "r", encoding="utf-8") as f:
            datos_token = json.load(f)

        id_cliente = datos_token.get("idCliente")
        jw_token = datos_token.get("JWToken")

        if not id_cliente or not jw_token:
            logger.error("❌ El JSON de token no contiene 'idCliente' o 'JWToken'.")
            return False

        headers = {
            "IdCliente": str(id_cliente),
            "Authorization": str(jw_token),
            "BaseDeDatos": "M-LIBRE",
            "Content-Type": "application/json",
        }

        articulos_totales = []
        page = 1
        limit_por_pagina = 200
        max_registros = 5000
        url_endpoint = f"{PRICER_API_URL}/Preciodearticulo/"

        logger.info("📥 Iniciando descarga de lista PUB (más reciente)...")

        while len(articulos_totales) < max_registros:
            params = {
                "ListaDePrecio": "PUB",
                "limit": limit_por_pagina,
                "page": page,
                "sort": "-FechaVigencia",  # Orden descendente por fecha más reciente
            }

            res = requests.get(
                url_endpoint, headers=headers, params=params, timeout=30
            )

            if res.status_code != 200:
                logger.error(
                    f"❌ Error HTTP {res.status_code} al consultar API: {res.text}"
                )
                return False

            data = res.json()
            resultados = data.get("Resultados", [])

            if not resultados:
                break

            for item in resultados:
                articulos_totales.append(
                    {
                        "Artículo": item.get("Articulo"),
                        "Precio": item.get("PrecioDirecto"),
                    }
                )

                if len(articulos_totales) >= max_registros:
                    break

            logger.info(
                f"   Página {page} procesada. Registros: {len(articulos_totales)} / {min(max_registros, data.get('TotalRegistros', max_registros))}"
            )

            if not data.get("Siguiente"):
                break

            page += 1

        if not articulos_totales:
            logger.warning("⚠️ La API no devolvió artículos.")
            return False

        # Guardar en data/PreciosDeArticulos.csv
        archivo_csv = DATA_DIR / "PreciosDeArticulos.csv"
        df = pd.DataFrame(articulos_totales)

        # encoding="utf-8-sig" asegura la correcta lectura de caracteres especiales
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")

        logger.info(f"✔ Archivo CSV guardado en: {archivo_csv}")
        return True

    except Exception as e:
        logger.error(f"❌ Error inesperado durante la descarga de precios: {e}")
        return False