# ==============================================================================
# ARCHIVO: views/html_view.py
# DESCRIPCIÓN: Clase encargada de generar el archivo HTML estático (index.html)
#              que renderiza el panel web de gestión de ventas de Mercado Libre.
# ==============================================================================

from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HTMLView:
    """
    Construye y exporta la estructura HTML del panel interactivo
    e inyecta las referencias a los archivos estáticos CSS y JS.
    """

    def __init__(
        self,
        output_file: str = "index.html",
        data_file: str = "views/js/temp_data.js",
    ):
        """
        Inicializa las rutas relativas para la salida del reporte web y datos temporales.
        """
        self.output_file = Path(output_file)
        self.data_file = Path(data_file)

    def generar_reporte(self, account_name: str, abrir_navegador: bool = True) -> None:
        """
        Genera la plantilla index.html inyectando la fecha actual, la cuenta activa,
        la barra de botones de acción y la estructura de la tabla de ventas.
        """
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        data_path_str = self.data_file.as_posix()

        # Contenido HTML maquetado
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel de Ventas MeLi</title>
    <link rel="icon" type="image/png" href="views/img/favicon.png" sizes="16x16" />
    <link rel="stylesheet" href="views/css/style.css">
</head>
<body>
    <!-- Encabezado con información general -->
    <div class="header">
        <h2>Panel de Ventas - Mercado Libre</h2>
        <p><strong>Fecha:</strong> {fecha_hoy} | <strong>Cuenta:</strong> {account_name}</p>
    </div>

    <!-- Panel de acciones globales (Selección, Impresión y Exportación) -->
    <div class="actions">
        <button class="btn-toggle" onclick="toggleSelectAll()">Tildar todas / Ninguna</button>
        <button id="btnRots" class="btn-generate btn-rojo" disabled onclick="imprimirRotulos()">Imprimir Rótulos</button>
        <button id="btnCSV" class="btn-generate" disabled onclick="generarCSV()">Generar Planilla CSV</button>
        <span id="cartelRenglones" class="cartel-renglones">Renglones: 0 / 20</span>
    </div>

    <!-- Tabla principal de ventas -->
    <table>
        <thead>
            <tr>
                <th><input type="checkbox" id="masterCheckbox" onclick="toggleSelectAll()"></th>
                <th>Fecha Venta</th>
                <th>ID Venta / Carrito</th>
                <th class="cliente">Cliente</th>
                <th>SKU</th>
                <th>Producto</th>
                <th>Variante</th>
                <th>Cant.</th>
                <th>Detalles</th>
                <th>Estado del Rótulo / Entrega</th>
            </tr>
        </thead>
        <tbody id="tablaVentas"></tbody>
    </table>

    <!-- Scripts de datos e interacción -->
    <script src="{data_path_str}"></script>
    <script src="views/js/scripts.js"></script>
</body>
</html>
"""

        # Guardado en disco
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Archivo HTML renderizado en {self.output_file}")

        # Apertura automática en el navegador predeterminado
        if abrir_navegador:
            import webbrowser
            webbrowser.open(self.output_file.resolve().as_uri())