# DescargaStock.py

"""
Controlador encargado de interactuar con la API de Dragonfish para 
descargar todo el stock sucursal por sucursal (código de talle, código de color como texto y stock entero),
sobrescribiendo siempre el archivo CSV en la ruta de red compartida.
"""

import json
import logging
from pathlib import Path
import pandas as pd
import requests

from config.settings import DATA_DIR, PRICER_API_URL, DBSTOCKS

logger = logging.getLogger("Stock")


def DescargaStock() -> bool:
    """
    Controlador principal de stock. Realiza lo siguiente:
    1. Define la ruta absoluta de red para sobrescribir siempre el archivo CSV.
    2. Lee credenciales y tokens de autenticación.
    3. Recorre de forma completa y paginada cada base de datos definida en DBSTOCKS.
    4. Extrae SKU, talle y color forzándolos estrictamente como TEXTO (para preservar ceros iniciales).
    5. Extrae el stock como número entero.
    6. Consolida y sobrescribe el CSV en la ruta de red (separado por ';') asegurando formato de texto.
    """
    # Ruta absoluta de red solicitada (se sobrescribirá siempre)
    archivo_csv = Path(r"\\EDGAR\Web\Listados de Ventas Online\StockDeArticulos.csv")

    # =========================================================================
    # PASO 1: LECTURA DE CREDENCIALES Y TOKENS
    # Función: Busca el archivo de token local, extrae el idCliente y JWToken,
    # y extrae el listado de bases de datos configuradas en DBSTOCKS.
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

        bases_stock = list(DBSTOCKS.values()) if isinstance(DBSTOCKS, dict) else list(DBSTOCKS)
        if not bases_stock:
            logger.error("❌ No hay bases de datos definidas en DBSTOCKS.")
            return False

        maestro_articulos = {}
        raw_resultados_total = []

        url_endpoint = f"{PRICER_API_URL}/ConsultaStockYPrecios/"
        limit_por_pagina = 200

        # =========================================================================
        # PASO 2: ITERACIÓN COMPLETA BASE POR BASE (PAGINACIÓN TOTAL)
        # Función: Recorre todas las páginas de cada sucursal de DBSTOCKS sin restricciones.
        # =========================================================================
        for nombre_base in bases_stock:
            logger.info(f"📥 Descargando todo el stock para la sucursal: [{nombre_base}] 🐟")

            headers = {
                "IdCliente": str(id_cliente),
                "Authorization": str(jw_token),
                "BaseDeDatos": str(nombre_base),
                "Content-Type": "application/json",
            }

            page = 1
            while True:
                params = {
                    "stockcero": "true",
                    "limit": limit_por_pagina,
                    "page": page,
                    "sort": "Articulo",
                }

                res = requests.get(
                    url_endpoint, headers=headers, params=params, timeout=60
                )

                if res.status_code != 200:
                    logger.error(
                        f"❌ Error HTTP {res.status_code} en base '{nombre_base}': {res.text}"
                    )
                    return False

                data = res.json()
                resultados = data.get("Resultados", [])

                if not resultados:
                    break

                raw_resultados_total.extend(resultados)

                # =====================================================================
                # PASO 3: PROCESAMIENTO (FORZANDO TEXTO EN SKU, COLOR, TALLE Y ENTERO EN STOCK)
                # =====================================================================
                for item in resultados:
                    # Forzar SKU, Talle y Color estrictamente como texto limpio
                    sku = str(item.get("Articulo", "")).strip()
                    if not sku:
                        continue

                    descripcion = str(item.get("ArticuloDescripcion", "")).strip()
                    talle = str(item.get("Talle", "")).strip()

                    # Controla si tiene datos y le agrega una comilla simple para asegurar que sea texto
                    if str(item.get("Color", "")).strip() != "":
                        color = "'" + str(item.get("Color", "")).strip()
                    

                    # Convertir stock explícitamente a número entero
                    try:
                        stock_actual = int(item.get("Stock", 0))
                    except (ValueError, TypeError):
                        stock_actual = 0

                    clave_unica = f"{sku}_{talle}_{color}"

                    if clave_unica not in maestro_articulos:
                        maestro_articulos[clave_unica] = {
                            "SKU": sku,
                            "DETALLE": descripcion,
                            "COLOR": color,
                            "TALLE": talle,
                        }
                        for b in bases_stock:
                            maestro_articulos[clave_unica][b] = 0

                    maestro_articulos[clave_unica][nombre_base] = stock_actual

                logger.info(f"   Sucursal '{nombre_base}' - Página {page} procesada ({len(resultados)} registros).")

                if len(resultados) < limit_por_pagina:
                    break

                page += 1

        if not maestro_articulos:
            logger.warning("⚠️ La API no devolvió artículos.")
            return False

        # =========================================================================
        # PASO 4: IMPRESIÓN, RESPALDO JSON Y GUARDADO EN CSV (RED) CON TIPADO DE TEXTO
        # =========================================================================
        articulos_totales = []
        for clave, articulo_data in maestro_articulos.items():
            articulos_totales.append(articulo_data)
            stocks_texto = " | ".join([f"{b}: {articulo_data[b]}" for b in bases_stock])
            print(f"SKU: {articulo_data['SKU']} | COLOR: {articulo_data['COLOR']} | TALLE: {articulo_data['TALLE']} | {stocks_texto}")

        # Guardar respaldo en JSON crudo local
        archivo_json_raw = DATA_DIR / "stock_raw.json"
        with open(archivo_json_raw, "w", encoding="utf-8") as f:
            json.dump(
                { "TotalProcesados": len(raw_resultados_total), "Resultados": raw_resultados_total },
                f,
                indent=4,
                ensure_ascii=False,
            )

        # Ordenar las columnas
        columnas_ordenadas = ["SKU", "DETALLE", "COLOR", "TALLE"] + bases_stock
        
        # Creamos el DataFrame forzando las columnas de texto a object/string explícitamente
        df = pd.DataFrame(articulos_totales)

        for col in columnas_ordenadas:
            if col not in df.columns:
                df[col] = 0

        df = df[columnas_ordenadas]

        # 1. Exportación y sobrescritura del CSV en la ruta absoluta de red (separado por ';')
        # Para evitar que Excel trunque los ceros a la izquierda (ej: "01" -> 1) al abrir el CSV directamente,
        # envolvemos los valores de COLOR y TALLE con formato de celda de texto para CSV (= "valor") o aseguramos el tipo.
        # Una práctica estándar muy segura en CSV para Excel es anteceder un apóstrofe o exportar limpio confiando en dtype.
        # Aquí utilizamos el formato estándar asegurando text tipado.
        archivo_csv.parent.mkdir(parents=True, exist_ok=True)
        
        # Nota: Para forzar absoluta compatibilidad con Excel en CSV sin perder ceros, 
        # se suele usar `="01"` o dejar que pandas lo escriba como texto plano entre comillas. 
        # Al usar `quoting=csv.QUOTE_NONNUMERIC` o simplemente exportando con `encoding="utf-8-sig"`, 
        # Pandas escribe las columnas string entre comillas dobles, lo que evita que Excel las interprete como números.
        df.to_csv(archivo_csv, index=False, sep=";", encoding="utf-8-sig", quoting=1)  # quoting=1 (QUOTE_ALL) o 2 (QUOTE_NONNUMERIC) fuerza comillas en texto
        logger.info(f"✔ Archivo CSV de red sobrescrito en: {archivo_csv} (con protección de texto para colores/talles)")

        return True

    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return False