"""
main.py
-------
Punto de entrada principal.
Coordina el flujo de selección de cuenta, ejecución del controlador y generación de la vista.
"""

import logging
import sys
from config.settings import CUENTAS, DATA_DIR
from controllers.meli_controller import MeLiController
from models.auth import MeLiAuth
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
    """Menú interactivo en consola."""
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
    # 1. Selección de Cuenta
    cuenta_config = seleccionar_cuenta()

    try:
        # 2. MODELO: Autenticación
        auth = MeLiAuth(cuenta_config)
        token = auth.get_access_token()

        # 3. CONTROLADOR: Descarga, Paginación y Filtrado de Órdenes
        controller = MeLiController(
            access_token=token, account_name=cuenta_config["nombre"]
        )
        ordenes_filtradas = controller.procesar_ventas_filtradas(
            limite_peticion=50
        )

        # 4. VISTA: Exportación JSON e HTML
        vista = HTMLView(output_file="index.html")
        vista.generar_reporte(
            account_name=cuenta_config["nombre"],
            ordenes=ordenes_filtradas,
            abrir_navegador=True,
        )

        print(
            f"\n✅ Proceso completado exitosamente para [{cuenta_config['nombre']}]."
        )

    except Exception as e:
        logging.error(f"Error crítico en la ejecución: {e}", exc_info=True)


if __name__ == "__main__":
    ejecutar()