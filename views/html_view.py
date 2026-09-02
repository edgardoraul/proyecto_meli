from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class HTMLView:
    def __init__(
        self,
        output_file: str = "index.html",
        data_file: str = "views/js/temp_data.js",
    ):
        self.output_file = Path(output_file)
        self.data_file = Path(data_file)

    def generar_reporte(self, account_name: str, abrir_navegador: bool = True) -> None:
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        data_path_str = self.data_file.as_posix()

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel de Ventas MeLi</title>
    <link rel="icon" type="image/png" href="views/img/favicon.png" sizes="16x16" />
    <link rel="stylesheet" href="views/css/style.css">
</head>
<body>
    <div class="header">
        <h2>Panel de Ventas - Mercado Libre</h2>
        <p><strong>Fecha:</strong> {fecha_hoy} | <strong>Cuenta:</strong> {account_name}</p>
    </div>

    <div class="actions">
        <button class="btn-toggle" onclick="toggleSelectAll()">Tildar todas / Ninguna</button>
        <button id="btnCSV" class="btn-generate" disabled onclick="generarCSV()">Generar Planilla CSV</button>
        <span id="cartelRenglones" class="cartel-renglones">Renglones: 0 / 20</span>
    </div>

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

    <script src="{data_path_str}"></script>
    <script src="views/js/scripts.js"></script>
</body>
</html>
"""

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Archivo HTML renderizado en {self.output_file}")

        if abrir_navegador:
            import webbrowser
            webbrowser.open(self.output_file.resolve().as_uri())