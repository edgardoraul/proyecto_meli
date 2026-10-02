# Archivo controller/DescargaPrecios.py

import json
import logging
import time
import pandas as pd
import requests

from config.settings import DATA_DIR, PRICER_API_URL, DBPRECIOS

logger = logging.getLogger("Pricer")


def DescargaPrecios() -> bool:
    archivo_csv = DATA_DIR / "PreciosDeArticulos.csv"

    # =========================================================================
    # SISTEMA DE CONTROL DE ANTIGÜEDAD (CACHE DE 30 MINUTOS)
    # Función: Verifica si el archivo 'PreciosDeArticulos.csv' ya existe y si su
    # última modificación fue hace menos de 30 minutos (1800 segundos). Si se
    # cumple la condición, omite la descarga vía API para no perder tiempo y
    # permite continuar directamente con los procesos siguientes.
    # =========================================================================
    TIEMPO_MAXIMO_SEGUNDOS = 30 * 60  # 30 minutos

    if archivo_csv.exists():
        antiguedad_segundos = time.time() - archivo_csv.stat().st_mtime
        if antiguedad_segundos < TIEMPO_MAXIMO_SEGUNDOS:
            minutos_transcurridos = int(antiguedad_segundos // 60)
            logger.info(
                f"⏩ Descarga omitida: El archivo '{archivo_csv.name}' fue generado hace {minutos_transcurridos} min "
                f"(antigüedad menor a 30 min). Se utilizarán los datos descargados previamente."
            )
            return True

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
            "BaseDeDatos": DBPRECIOS[0],
            "Content-Type": "application/json",
        }

        articulos_totales = []
        raw_resultados = []

        # Conjunto para desduplicar por código de artículo
        articulos_vistos = set()

        page = 1
        limit_por_pagina = 200
        url_endpoint = f"{PRICER_API_URL}/ConsultaStockYPrecios/"

        logger.info("📥 Iniciando descarga completa de lista PUB desde Dragonfish...")

        while True:
            # CAMBIO PRINCIPAL: Parámetros corregidos según documentación oficial
            # 1. 'lista' en lugar de 'ListaDePrecio'
            # 2. 'stockcero': "true" en minúsculas para incluir artículos sin stock
            # 3. 'preciocero': "false" para omitir artículos sin precio
            params = {
                "lista": "PUB",
                "stockcero": "true",
                "preciocero": "false",
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

                if not cod_articulo or cod_articulo in articulos_vistos:
                    continue

                precios = item.get("Precios", [])

                # Extraer el precio de la lista de precios o el del nivel raíz
                precio_publico = next(
                    (
                        p.get("Precio")
                        for p in precios
                        if str(p.get("Lista")).strip().upper() in ("PUB", "PÚBLICO", "PUBLICO")
                    ),
                    item.get("Precio"),
                )

                articulos_totales.append(
                    {
                        "Articulo": cod_articulo,
                        "Precio": precio_publico,
                    }
                )
                articulos_vistos.add(cod_articulo)

            total_api = data.get("TotalRegistros", "Desconocido")
            logger.info(
                f"   Página {page} procesada ({len(resultados)} recs). Artículos únicos acumulados: {len(articulos_totales)} / Total API: {total_api}"
            )

            # Condición de salida cuando se procesan todos los registros
            if len(resultados) < limit_por_pagina:
                break

            page += 1

        if not raw_resultados:
            logger.warning("⚠️ La API no devolvió artículos.")
            return False

        # Guardar respuesta cruda completa
        archivo_json_raw = DATA_DIR / "precios_raw.json"
        with open(archivo_json_raw, "w", encoding="utf-8") as f:
            json.dump(
                {"TotalProcesados": len(raw_resultados), "Resultados": raw_resultados},
                f,
                indent=4,
                ensure_ascii=False,
            )
        logger.info(f"✔ Estructura cruda JSON guardada en: {archivo_json_raw}")

        # Guardar CSV consolidado
        df = pd.DataFrame(articulos_totales)
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")

        logger.info(f"✔ Archivo CSV guardado en: {archivo_csv}")
        return True

    except Exception as e:
        logger.error(f"❌ Error inesperado durante la descarga de precios: {e}")
        return False