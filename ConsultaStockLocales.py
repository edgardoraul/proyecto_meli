"""
Punto de entrada principal para la consulta y descarga de stock entre locales
desde la API de Dragonfish (Pricer).
"""

import logging
import sys
from config.settings import DATA_DIR
from controllers.DescargaStock import DescargaStock

# =====================================================================
# CONFIGURACIÓN DEL SISTEMA DE LOGS
# =====================================================================
# Define cómo y dónde se registrarán los mensajes de ejecución (consola y archivo).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "ejecucion_stock.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def ejecutar():
    """
    Función orquestadora que inicia el proceso de gestión de stock.
    Muestra un encabezado en consola y controla las excepciones generales.
    """
    print("\n==============================================")
    print("       GESTIÓN DE STOCK - DRAGONFISH          ")
    print("==============================================")

    try:
        print("\n🚀 Iniciando proceso de consultas de stock entre locales y/o sucursales ...")
        
        # Llamada al controlador que encapsula la lógica de descarga
        exito = DescargaStock()

        if exito:
            print("\n✅ Proceso completado exitosamente.")
        else:
            print("\n❌ Hubo un error durante la descarga del stock. Revisar logs.")
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error crítico en la ejecución: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    ejecutar()