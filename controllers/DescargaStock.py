"""
Controlador encargado de interactuar con la API de Dragonfish para 
descargar el stock consolidado entre sucursales y guardarlo en un archivo CSV.
"""

import json
import logging
import time
import pandas as pd
import requests

from config.settings import DATA_DIR, PRICER_API_URL, DBSTOCKS

logger = logging.getLogger("Stock")


def DescargaStock() -> bool:
    """
    Controlador principal de stock. Realiza lo siguiente:
    1. Verifica si existe un archivo CSV reciente (caché de 30 minutos).
    2. Lee las credenciales y el token de autenticación desde el almacenamiento local.
    3. Realiza solicitudes paginadas al endpoint '/ConsultaStockYPreciosEntreLocales/' con timeout ampliado.
    4. Muestra en tiempo real por consola cada artículo procesado.
    5. Exporta el resultado final en el orden de columnas solicitado.
    """
    archivo_csv = DATA_DIR / "StockDeArticulos.csv"

    # =========================================================================
    # PASO 1: SISTEMA DE CONTROL DE ANTIGÜEDAD (CACHE DE 30 MINUTOS)
    # =========================================================================
    TIEMPO_MAXIMO_SEGUNDOS = 30 * 60  # 30 minutos

    if archivo_csv.exists():
        antiguedad_segundos = time.time() - archivo_csv.stat().st_mtime
        if antiguedad_segundos < TIEMPO_MAXIMO_SEGUNDOS:
            minutos_transcurridos = int(antiguedad_segundos // 60)
            logger.info(
                f"⏩ Descarga de stock omitida: El archivo '{archivo_csv.name}' fue generado hace {minutos_transcurridos} min "
                f"(antigüedad menor a 30 min). Se utilizarán los datos previos."
            )
            return True

    # =========================================================================
    # PASO 2: LECTURA DE CREDENCIALES Y TOKENS
    # =========================================================================
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

        # Extraer las bases de datos configuradas (ej: PIEZA, MENDOZA, TUCUMAN)
        bases_stock = list(DBSTOCKS.values()) if isinstance(DBSTOCKS, dict) else list(DBSTOCKS)
        base_principal = bases_stock[0] if bases_stock else "PIEZA"

        headers = {
            "IdCliente": str(id_cliente),
            "Authorization": str(jw_token),
            "BaseDeDatos": str(base_principal),
            "Content-Type": "application/json",
        }

        articulos_totales = []
        raw_resultados = []
        articulos_vistos = set()

        page = 1
        limit_por_pagina = 200
        url_endpoint = f"{PRICER_API_URL}/ConsultaStockYPreciosEntreLocales/"

        logger.info("📥 Descargando stock entre locales desde Dragonfish 🐟")

        # =========================================================================
        # PASO 3: BUCLE DE PAGINACIÓN Y CONSUMO DE LA API
        # =========================================================================
        while True:
            params = {
                "limit": limit_por_pagina,
                "page": page
            }

            # Timeout aumentado a 90 segundos para evitar cortes por respuestas lentas del ERP
            res = requests.get(
                url_endpoint, headers=headers, params=params, timeout=90
            )

            if res.status_code != 200:
                logger.error(
                    f"❌ Error HTTP {res.status_code} al consultar API de stock: {res.text}"
                )
                return False

            data = res.json()
            resultados = data.get("Resultados", [])

            if not resultados:
                break

            raw_resultados.extend(resultados)

            # =====================================================================
            # PASO 4: PROCESAMIENTO Y VISUALIZACIÓN LÍNEA A LÍNEA EN CONSOLA
            # =====================================================================
            for item in resultados:
                sku = item.get("Articulo")
                if not sku:
                    continue

                descripcion = item.get("ArticuloDescripcion", "")
                talle = item.get("Talle", "")
                color = item.get("ColorDescripcion", "")

                stocks_array = item.get("Stock", [])

                fila_articulo = {
                    "SKU": sku,
                    "Descripción": descripcion,
                    "talle": talle,
                    "color": color,
                }

                # Extraer stock de cada base configurada
                for nombre_base in bases_stock:
                    stock_valor = 0
                    for s_obj in stocks_array:
                        if str(s_obj.get("BasedeDatos", "")).strip().upper() == str(nombre_base).strip().upper():
                            stock_valor = s_obj.get("Stock", 0)
                            break
                    fila_articulo[nombre_base] = stock_valor

                # Control de unicidad por SKU, talle y color
                clave_unica = f"{sku}_{talle}_{color}"
                if clave_unica in articulos_vistos:
                    continue

                articulos_totales.append(fila_articulo)
                articulos_vistos.add(clave_unica)

                # 🖨️ Muestra línea a línea en la consola el progreso detallado
                stocks_texto = " | ".join([f"{base}: {fila_articulo[base]}" for base in bases_stock])
                print(f"SKU: {sku} | Talle: {talle} | Color: {color} | {stocks_texto}")

            total_api = data.get("TotalRegistros", "Desconocido")
            logger.info(
                f"   Página {page} procesada con éxito. Artículos acumulados: {len(articulos_totales)} / Total API: {total_api}"
            )

            if len(resultados) < limit_por_pagina:
                break

            page += 1

        if not raw_resultados:
            logger.warning("⚠️ La API de stock no devolvió artículos.")
            return False

        # =========================================================================
        # PASO 5: GUARDADO DE RESPUESTA CRUDA Y CONSOLIDACIÓN EN CSV
        # =========================================================================
        archivo_json_raw = DATA_DIR / "stock_raw.json"
        with open(archivo_json_raw, "w", encoding="utf-8") as f:
            json.dump(
                {"TotalProcesados": len(raw_resultados), "Resultados": raw_resultados},
                f,
                indent=4,
                ensure_ascii=False,
            )

        columnas_ordenadas = ["SKU", "Descripción", "talle", "color"] + bases_stock
        df = pd.DataFrame(articulos_totales)

        for col in columnas_ordenadas:
            if col not in df.columns:
                df[col] = 0

        df = df[columnas_ordenadas]
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")

        logger.info(f"✔ Archivo CSV de stock guardado en: {archivo_csv}")
        return True

    except Exception as e:
        logger.error(f"❌ Error inesperado durante la descarga de stock: {e}")
        return False