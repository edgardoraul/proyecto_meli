import subprocess
import sys

# Lista de librerías externas que requiere tu proyecto. Chequea e instala lo que falta
PAQUETES_REQUERIDOS = ["requests"]

def verificar_dependencias():
    for paquete in PAQUETES_REQUERIDOS:
        try:
            # Intenta importar. Si está instalada, pasa de largo al instante.
            __import__(paquete)
        except ImportError:
            # Solo si no existe (primera vez), la instala por consola.
            print(f"📦 Instalando dependencia por primera vez: {paquete}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", paquete])

# Se ejecuta al iniciar el script
verificar_dependencias()

# =============================================================
# DESDE AQUÍ VAN TUS IMPORTS Y CÓDIGO HABITUAL DE MAIN.PY
# =============================================================
import logging
import sys
from config.settings import CUENTAS, DATA_DIR
from controllers.meli_controller import MeLiController
from models.auth import MeLiAuth
from models.order import Order
from views.html_view import HTMLView

# Logger global
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "ejecucion.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def seleccionar_cuenta() -> dict:
    print("\n==============================================")
    print("      PANEL DE GESTIÓN DE MERCADO LIBRE       ")
    print("==============================================")

    if not CUENTAS:
        print("❌ No hay cuentas configuradas en el archivo .env")
        sys.exit(1)

    for key, data in CUENTAS.items():
        print(f" [{key}] {data['nombre']}")

    print(" [0] Salir")
    print("----------------------------------------------")

    opcion = input("Seleccioná la cuenta a procesar: ").strip()

    if opcion == "0":
        print("Saliendo...")
        sys.exit(0)

    if opcion in CUENTAS:
        return CUENTAS[opcion]
    else:
        print("\n[!] Opción inválida. Intente de nuevo.")
        return seleccionar_cuenta()


def ejecutar():
    cuenta_config = seleccionar_cuenta()

    try:
        # 1. Autenticación
        auth = MeLiAuth(cuenta_config)
        token = auth.get_access_token()

        # 2. Descarga del JSON con envíos y notas en paralelo
        controller = MeLiController(
            access_token=token, account_name=cuenta_config["nombre"]
        )
        json_path = controller.descargar_ultimas_ventas(limite=20)

        # 3. Parseo del JSON a objetos Order (ordenados por fecha desc)
        ordenes = Order.cargar_desde_json(json_path)

        # 4. Generación de la vista HTML
        vista = HTMLView(output_file="index.html")
        vista.generar_reporte(
            account_name=cuenta_config["nombre"],
            ordenes=ordenes,
            abrir_navegador=True,
        )

        print(
            f"\n✅ Proceso completado exitosamente para [{cuenta_config['nombre']}]."
        )

    except Exception as e:
        logging.error(f"Error crítico en la ejecución: {e}", exc_info=True)


if __name__ == "__main__":
    ejecutar()