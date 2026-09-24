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
        raw_resultados = []
        articulos_vistos = set()  # Conjunto para desduplicar por código de artículo
        page = 1
        limit_por_pagina = 200
        max_registros = 5000
        url_endpoint = f"{PRICER_API_URL}/ConsultaStockYPrecios/"

        logger.info("📥 Iniciando descarga de lista PUB (más reciente)...")

        while len(articulos_totales) < max_registros:
            params = {
                "ListaDePrecio": "PUB",
                "limit": limit_por_pagina,
                "page": page,
                "sort": "Articulo",
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

            raw_resultados.extend(resultados)

            for item in resultados:
                cod_articulo = item.get("Articulo")

                # Omitir si ya agregamos este código de artículo previamente
                if not cod_articulo or cod_articulo in articulos_vistos:
                    continue

                precios = item.get("Precios", [])

                # Busca el precio específico de la lista "Público"
                precio_publico = next(
                    (p.get("Precio") for p in precios if p.get("Lista") == "Público"),
                    item.get("Precio"),  # Fallback si no está la lista "Público"
                )

                articulos_totales.append(
                    {
                        "Artículo": cod_articulo,
                        "Precio": precio_publico,
                    }
                )
                articulos_vistos.add(cod_articulo)

                if len(articulos_totales) >= max_registros:
                    break

            logger.info(
                f"   Página {page} procesada. Artículos únicos: {len(articulos_totales)} / {min(max_registros, data.get('TotalRegistros', max_registros))}"
            )

            if not data.get("Siguiente"):
                break

            page += 1

        if not raw_resultados:
            logger.warning("⚠️ La API no devolvió artículos.")
            return False

        # Guardar respuesta cruda completa para análisis
        archivo_json_raw = DATA_DIR / "precios_raw.json"
        with open(archivo_json_raw, "w", encoding="utf-8") as f:
            json.dump(
                {"TotalProcesados": len(raw_resultados), "Resultados": raw_resultados},
                f,
                indent=4,
                ensure_ascii=False,
            )
        logger.info(f"✔ Estructura cruda JSON guardada en: {archivo_json_raw}")

        # Guardar CSV con artículos únicos
        archivo_csv = DATA_DIR / "PreciosDeArticulos.csv"
        df = pd.DataFrame(articulos_totales)
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")

        logger.info(f"✔ Archivo CSV guardado en: {archivo_csv}")
        return True

    except Exception as e:
        logger.error(f"❌ Error inesperado durante la descarga de precios: {e}")
        return False