// Limpieza de carritos: recorremos de abajo hacia arriba.
// Asume que 'ventasData' ya fue cargada globalmente por temp_data.js
for (let i = ventasData.length - 1; i > 0; i--) {
    if (ventasData[i].venta_id === ventasData[i - 1].venta_id) {
        ventasData[i].fecha = "";
        ventasData[i].venta_id = "";
        ventasData[i].cliente = "";
        ventasData[i].numero_guia = "";
        ventasData[i].texto_rotulo = "";
        ventasData[i].estado_rotulo = "";
    }
}

function cargarTabla() {
    const tbody = document.getElementById('tablaVentas');
    if (!tbody) return;
    tbody.innerHTML = '';

    ventasData.forEach((v, index) => {
        let skusHtml = '<ul class="item-list">';
        let titulosHtml = '<ul class="item-list">';
        let variantesHtml = '<ul class="item-list">';
        let cantidadesHtml = '<ul class="item-list">';

        v.items.forEach(item => {
            skusHtml += `<li class="item-row"><strong>${item.sku}</strong></li>`;
            titulosHtml += `<li class="item-row">${item.titulo}</li>`;
            variantesHtml += `<li class="item-row">${item.variante}</li>`;
            cantidadesHtml += `<li class="item-row">${item.cantidad}</li>`;
        });

        skusHtml += '</ul>';
        titulosHtml += '</ul>';
        variantesHtml += '</ul>';
        cantidadesHtml += '</ul>';

        // Determinar si lleva borde superior (es una nueva orden y no es la primera fila)
        let trClass = (index > 0 && v.venta_id !== "") ? ' class="borde-separador"' : '';

        tbody.innerHTML += `<tr${trClass}>
            <td><input type="checkbox" class="row-checkbox" value="${index}" onchange="actualizarBoton()"></td>
            <td>${v.fecha}</td>
            <td><strong>${v.venta_id}</strong></td>
            <td><strong>${v.cliente}</strong></td>
            <td>${skusHtml}</td>
            <td>${titulosHtml}</td>
            <td>${variantesHtml}</td>
            <td>${cantidadesHtml}</td>
            <td>${v.detalles || ''}</td>
            <td><span class="badge badge-${v.estado_rotulo}">${v.texto_rotulo}</span></td>
        </tr>`;
    });
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    const master = document.getElementById('masterCheckbox');
    const nuevoEstado = !Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = nuevoEstado);
    if (master) master.checked = nuevoEstado;
    actualizarBoton();
}

function actualizarBoton() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    const btn = document.getElementById('btnCSV');
    if (!btn) return;
    btn.disabled = checkboxes.length === 0;
    btn.classList.toggle('active', checkboxes.length > 0);
}

function generarCSV() {
    const seleccionados = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => parseInt(cb.value));
    let csvLines = [["Nº Venta", "Cliente", "Código", "Producto", "Cantidad", "Detalles", "Nº Guía"].join(";")];

    seleccionados.forEach(idx => {
        const v = ventasData[idx];
        v.items.forEach(item => {
            let idVentaFormateado = v.venta_id ? `"\'${v.venta_id}"` : '""';
            let guiaFormateada = v.numero_guia ? `"${v.numero_guia}"` : '""';

            csvLines.push([
                idVentaFormateado,
                `"${v.cliente}"`,
                `"${item.sku}"`,
                `"${item.titulo}"`,
                // `"${item.variante}"`,
                item.cantidad,
                `"${v.detalles || ''}"`,
                guiaFormateada
            ].join(";"));
        });
    });

    const encodedUri = encodeURI("data:text/csv;charset=utf-8,\uFEFF" + csvLines.join("\n"));
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "planilla_ventas_seleccionadas.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

document.addEventListener('DOMContentLoaded', cargarTabla);