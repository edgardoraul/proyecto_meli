"""
views/html_view.py
------------------
Vista encargada de generar el archivo 'index.html' y actualizar 'views/js/scripts.js'
adaptado a la tabla interactiva y exportación a CSV.
"""

import json
import logging
import webbrowser
from pathlib import Path
from typing import List

from models.order import Order

logger = logging.getLogger(__name__)


class HTMLView:
    """Genera la interfaz de tabla interactiva basada en las órdenes procesadas."""

    def __init__(
        self,
        output_file: str = "index.html",
        js_file: str = "views/js/scripts.js",
    ):
        self.output_file = Path(output_file)
        self.js_file = Path(js_file)

    def _mapear_color_badge(self, estado: str) -> str:
        """Asigna el color del badge según el estado mapeado."""
        colores = {
            "Imprimir Rótulo": "Naranja",
            "Rótulo Impreso": "Naranja",
            "A coordinar con el vendedor": "Gris",
            "Retiro en local": "Gris",
        }
        return colores.get(estado, "Gris")

    def exportar_js_data(self, ordenes: List[Order]) -> None:
        """
        Genera/actualiza el archivo 'views/js/scripts.js' inyectando
        la variable JS 'ventasData' con las órdenes reales de la API.
        """
        ventas_list = []

        for orden in ordenes:
            ventas_list.append(
                {
                    "venta_id": orden.venta_id,
                    "fecha": orden.date_created.split("T")[0]
                    if "T" in orden.date_created
                    else orden.date_created,
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

        # Convertimos la lista de Python a formato JSON
        json_data_str = json.dumps(ventas_list, indent=4, ensure_ascii=False)

        # Código JS base con las funciones de tabla y exportación CSV
        js_content = f"""const ventasData = {json_data_str};

function cargarTabla() {{
    const tbody = document.getElementById('tablaVentas');
    if (!tbody) return;
    tbody.innerHTML = '';
    ventasData.forEach((v, index) => {{
        let skusHtml = '<ul class="item-list">', variantesHtml = '<ul class="item-list">', cantidadesHtml = '<ul class="item-list">';
        v.items.forEach(item => {{
            skusHtml += `<li class="item-row"><strong>${{item.sku}}</strong></li>`;
            variantesHtml += `<li class="item-row">${{item.variante}}</li>`;
            cantidadesHtml += `<li class="item-row">${{item.cantidad}}</li>`;
        }});
        tbody.innerHTML += `<tr>
                    <td><input type="checkbox" class="row-checkbox" value="${{index}}" onchange="actualizarBoton()"></td>
                    <td>${{v.fecha}}</td>
                    <td><strong>${{v.venta_id}}</strong></td>
                    <td><strong>${{v.cliente}}</strong></td>
                    <td>${{skusHtml}}</ul></td>
                    <td>${{variantesHtml}}</ul></td>
                    <td>${{cantidadesHtml}}</ul></td>
                    <td>${{v.detalles || ''}}</td>
                    <td><span class="badge badge-${{v.estado_rotulo}}">${{v.texto_rotulo}}</span></td>
                </tr>`;
    }});
}}

function toggleSelectAll() {{
    const checkboxes = document.querySelectorAll('.row-checkbox');
    const master = document.getElementById('masterCheckbox');
    const nuevoEstado = !Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = nuevoEstado);
    if (master) master.checked = nuevoEstado;
    actualizarBoton();
}}

function actualizarBoton() {{
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    const btn = document.getElementById('btnCSV');
    if (!btn) return;
    btn.disabled = checkboxes.length === 0;
    btn.classList.toggle('active', checkboxes.length > 0);
}}

function generarCSV() {{
    const seleccionados = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => parseInt(cb.value));
    let csvLines = [["ID Venta / Carrito", "Cliente", "SKU", "Variante", "Cantidad", "Detalles", "Numero Guia / Retiro"].join(";")];
    seleccionados.forEach(idx => {{
        const v = ventasData[idx];
        v.items.forEach(item => {{
            csvLines.push([`"'${{v.venta_id}}"`, `"${{v.cliente}}"`, `"${{item.sku}}"`, `"${{item.variante}}"`, item.cantidad, `"${{v.detalles || ''}}"`, `"${{v.numero_guia}}"`].join(";"));
        }});
    }});
    const encodedUri = encodeURI("data:text/csv;charset=utf-8,\\uFEFF" + csvLines.join("\\n"));
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "planilla_ventas_seleccionadas.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}}

// Carga inicial al ejecutar la página
document.addEventListener('DOMContentLoaded', cargarTabla);
"""

        # Aseguramos existencia del directorio
        self.js_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.js_file, "w", encoding="utf-8") as f:
            f.write(js_content)

        logger.info(f"Script JS y datos inyectados en {self.js_file}")

    def generar_reporte(
        self, account_name: str, ordenes: List[Order], abrir_navegador: bool = True
    ) -> None:
        """Genera el HTML que estructura la tabla de ventas."""
        # 1. Inyectamos las ordenes al script JS
        self.exportar_js_data(ordenes)

        # 2. Plantilla HTML adaptada
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Ventas - {account_name}</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA7EAAAOxAGVKw4bAAACBUlEQVQ4jZWTTWtTURCGn3Nycu+N4ba2kqDGkJIiigpiVk2DghHpn0gFN2JJFgp2Z/IHSkWh/6ChGxfdWLsQUlAkFYu60IKFBvGiNEUQ/KC9+bjHRZM2bS9CB2Zxzpx5Z+Y98woOW9IyyWXTMp2Mi5MANUdvVKpeddulDNR8cgAw7DDTxbxy68tm21uzdK/Xl812Ma9cO8wUYBxKTsTE4sq8cSjxoK/MG+1ETCx2QQSAHWZ6qWzcS12U8m4Jfv3R+9CP98H925KziZ37d58873qu8ej3XyYBksW8crsVIoNSAxrQly+E9MS4rR/csXXqkqk/vwjtdlLMKxcYkpZJrjAeUH6kCAHBoObNhwZj1wxKT7zdWGE8oCyTnMqmZToyKKQvq0GN863JyBXFq7dNgkHZaQ4ig0Jm0zIju1/lZ/UfHjUHQpZkoA+aLbEvPhwXUd/ premature230284848" sizes="16x16" />
    <link rel="stylesheet" href="views/css/style.css">
</head>
<body>

    <h1>Panel de Ventas Operativas - {account_name}</h1>

    <div class="controls">
        <button onclick="toggleSelectAll()">Seleccionar Todo</button>
        <button id="btnCSV" onclick="generarCSV()" disabled>Generar CSV</button>
    </div>

    <table border="1" style="width: 100%; border-collapse: collapse; text-align: left;">
        <thead>
            <tr>
                <th><input type="checkbox" id="masterCheckbox" onclick="toggleSelectAll()"></th>
                <th>Fecha</th>
                <th>ID Venta</th>
                <th>Cliente</th>
                <th>SKUs</th>
                <th>Variantes</th>
                <th>Cantidades</th>
                <th>Detalles</th>
                <th>Estado</th>
            </tr>
        </thead>
        <tbody id="tablaVentas">
            <!-- Cargado dinámicamente mediante scripts.js -->
        </tbody>
    </table>

    <script src="views/js/scripts.js"></script>
</body>
</html>
"""

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Archivo HTML generado exitosamente en {self.output_file}")

        if abrir_navegador:
            webbrowser.open(self.output_file.resolve().as_uri())