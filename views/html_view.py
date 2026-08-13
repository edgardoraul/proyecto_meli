"""
views/html_view.py
------------------
Vista encargada de generar el archivo 'index.html' con la estética limpia.
Genera los datos en un archivo JS temporal y delega la lógica a views/js/scripts.js.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List

from models.order import Order

logger = logging.getLogger(__name__)


class HTMLView:
    def __init__(
        self,
        output_file: str = "index.html",
        data_file: str = "views/js/temp_data.js",
    ):
        self.output_file = Path(output_file)
        self.data_file = Path(data_file)

    def _mapear_color_badge(self, estado: str) -> str:
        colores = {
            "Imprimir Rótulo": "NaranjaClaro",
            "Rótulo Impreso": "Naranja",
            "Retiro en local": "Gris",
            "A coordinar con el vendedor": "Gris",
        }
        return colores.get(estado, "Gris")

    def exportar_js_data(self, ordenes: List[Order]) -> None:
        """Inyecta ÚNICAMENTE los datos procesados en un script JS temporal."""
        ventas_list = []

        for orden in ordenes:
            fecha_fmt = (
                orden.date_created.split("T")[0]
                if "T" in orden.date_created
                else orden.date_created
            )

            ventas_list.append(
                {
                    "venta_id": orden.venta_id,
                    "fecha": fecha_fmt,
                    "cliente": orden.buyer_nickname,
                    "estado_rotulo": self._mapear_color_badge(
                        orden.estado_humano
                    ),
                    "texto_rotulo": orden.estado_humano,
                    "numero_guia": orden.tracking_number,
                    "detalles": orden.seller_note,
                    "items": [
                        {
                            "sku": item.sku,
                            "variante": item.variant,
                            "cantidad": item.quantity,
                        }
                        for item in orden.items
                    ],
                }
            )

        json_data_str = json.dumps(ventas_list, indent=4, ensure_ascii=False)
        js_content = f"const ventasData = {json_data_str};\n"

        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            f.write(js_content)

        logger.info(f"Datos exportados a {self.data_file}")

    def generar_reporte(
        self, account_name: str, ordenes: List[Order], abrir_navegador: bool = True
    ) -> None:
        self.exportar_js_data(ordenes)

        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        data_path_str = self.data_file.as_posix()

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel de Ventas MeLi</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA7EAAAOxAGVKw4bAAACBUlEQVQ4jZWTTWtTURCGn3Nycu+N4ba2kqDGkJIiigpiVk2DghHpn0gFN2JJFgp2Z/IHSkWh/6ChGxfdWLsQUlAkFYu60IKFBvGiNEUQ/KC9+bjHRZM2bS9CB2Zxzpx5Z+Y98woOW9IyyWXTMp2Mi5MANUdvVKpeddulDNR8cgAw7DDTxbxy68tm21uzdK/Xl812Ma9cO8wUYBxKTsTE4sq8cSjxoK/MG+1ETCx2QQSAHWZ6qWzcS12U8m4Jfv3R+9CP98H925KziZ37d58873qu8ej3XyYBksW8crsVIoNSAxrQly+E9MS4rR/csXXqkqk/vwjtdlLMKxcYkpZJrjAeUH6kCAHBoObNhwZj1wxKT7zdWGE8oCyTnMqmZToyKKQvq0GN863JyBXFq7dNgkHZaQ4ig0Jm0zIju1/lZ/UfHjUHQpZkoA+aLbEvPhwXUd/Wu9ZvS0ZTkoVKgxsZxdZWq8t7Z0ZQNUdv/A8EoTg/rHm+1ODlnNodAWD9q97EMin1Lk7vL/R6/LTS7mpo32JZJg/ltkt5Zrbd8it+LLTHrfO9xdyzveozs+3Wtks5APx8v+r1j12VI6eiQnxcEwydkZxLBijcMjgxECAR2zlrHeDm6M4iTZSajxtNnnYBj7rKC/jpwQ4zdVQxiYMowFBHzpnhuIgCrDt6s1L1Xnfk/KX38T9T2xqsmAW/oAAAAABJRU5ErkJggg==" sizes="16x16" />
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
    </div>

    <table>
        <thead>
            <tr>
                <th><input type="checkbox" id="masterCheckbox" onclick="toggleSelectAll()"></th>
                <th>Fecha Venta</th>
                <th>ID Venta / Carrito</th>
                <th>Cliente</th>
                <th>SKU</th>
                <th>Variante</th>
                <th>Cant.</th>
                <th>Detalles</th>
                <th>Estado del Rótulo / Entrega</th>
            </tr>
        </thead>
        <tbody id="tablaVentas"></tbody>
    </table>

    <!-- Primero se cargan los datos crudos -->
    <script src="{data_path_str}"></script>
    <!-- Luego se carga la lógica del negocio -->
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