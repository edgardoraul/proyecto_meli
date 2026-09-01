let ventasData = [];

// Convierte TEMP_DATA (JSON crudo) al formato estructurado para la tabla
function convertirRawData() {
    if (typeof TEMP_DATA === 'undefined') {
        console.error("❌ No se encontró la variable TEMP_DATA en temp_data.js");
        return;
    }

    const rawOrders = Array.isArray(TEMP_DATA) ? TEMP_DATA : (TEMP_DATA.results || []);

    if (!rawOrders.length) {
        console.warn("⚠️ TEMP_DATA está vacío o no contiene resultados.");
        return;
    }
    // Estados de interes: Imprimir Rótulo, Rótulo Impreso, Retiro del Local, A coordinar.
    // El resto no importa, sólo mostrar los que están en tránsito

    const SUBESTADOS_IMPRIMIR = new Set(["ready_to_print"]);
    const SUBESTADOS_IMPRESO = new Set(["printed"]);
    const SUBESTADOS_EN_VIAJE = new Set(["picked_up", "authorized_by_carrier", "in_transit", "out_for_delivery"]);
    const ESTADOS_EN_VIAJE = new Set(["shipped"]);
    const LOGISTICA_LOCAL = new Set(["custom", "not_specified", "pickup", "store"]);
    const ESTADOS_LOCAL = new Set(["to_be_agreed"]);

    ventasData = rawOrders.map(order => {
        const ship = order.shipping_info;
        const substatus = ship.substatus;
        const status = ship.status;
        const logisticType = ship.logistic_type;

        let texto_rotulo;
        let estado_rotulo;

        if (SUBESTADOS_IMPRIMIR.has(substatus)) {
            texto_rotulo = "Imprimir rótulo";
            estado_rotulo = "Verde";
        } else if (SUBESTADOS_IMPRESO.has(substatus)) {
            texto_rotulo = "Rótulo impreso";
            estado_rotulo = "Naranja";
        } else if (LOGISTICA_LOCAL.has(logisticType) || ESTADOS_LOCAL.has(status)) {
            texto_rotulo = "Retiro en Local";
            estado_rotulo = "NaranjaClaro";
        } else if (SUBESTADOS_EN_VIAJE.has(substatus) || ESTADOS_EN_VIAJE.has(status)) {
            texto_rotulo = "En viaje";
            estado_rotulo = "Gris";
        } else {
            texto_rotulo = order.status;
            estado_rotulo = "Gris";
        }

        const dateObj = new Date(order.date_created);
        const fecha = isNaN(dateObj) ? "" : dateObj.toLocaleString('es-AR', {
            day: '2-digit', month: '2-digit', year: 'numeric'
        });

        const buyer = order.buyer || {};
        const cliente = buyer.nickname || `${buyer.first_name || ''} ${buyer.last_name || ''}`.trim() || "Cliente MeLi";

        const items = (order.order_items || []).map(oi => {
            const item = oi.item || {};
            let variante = "-";
            if (item.variation_attributes && item.variation_attributes.length > 0) {
                variante = item.variation_attributes.map(a => `${a.name}: ${a.value_name}`).join(", ");
            }

            return {
                sku: item.seller_sku,
                titulo: item.title,
                variante: variante,
                cantidad: oi.quantity
            };
        });

        return {
            venta_id: String(order.pack_id || order.id || ""),
            fecha: fecha,
            cliente: cliente,
            numero_guia: String(ship.tracking_number || ship.id || ""),
            detalles: order.notes || "",
            texto_rotulo: texto_rotulo,
            estado_rotulo: estado_rotulo,
            items: items
        };
    });
}

// Limpieza de datos repetidos en carritos
function limpiarCarritos() {
    for (let i = ventasData.length - 1; i > 0; i--) {
        if (ventasData[i].venta_id && ventasData[i].venta_id === ventasData[i - 1].venta_id) {
            ventasData[i].fecha = "";
            ventasData[i].venta_id = "";
            ventasData[i].cliente = "";
            ventasData[i].numero_guia = "";
            ventasData[i].texto_rotulo = "";
            ventasData[i].estado_rotulo = "";
        }
    }
}

// Carga del HTML de la tabla
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
    const cartel = document.getElementById('cartelRenglones');

    let totalRenglones = 0;
    checkboxes.forEach(cb => {
        const idx = parseInt(cb.value);
        if (ventasData[idx] && ventasData[idx].items) {
            totalRenglones += ventasData[idx].items.length;
        }
    });

    if (cartel) {
        if (totalRenglones > 20) {
            cartel.textContent = `Renglones: ${totalRenglones} / 20 (¡Supera el límite!)`;
            cartel.style.color = "#d9534f";
            cartel.style.fontWeight = "bold";
        } else {
            cartel.textContent = `Renglones: ${totalRenglones} / 20`;
            cartel.style.color = "#333";
            cartel.style.fontWeight = "normal";
        }
    }

    if (!btn) return;

    const esValido = totalRenglones > 0 && totalRenglones <= 20;
    btn.disabled = !esValido;
    btn.classList.toggle('active', esValido);
}

function generarCSV() {
    const seleccionados = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => parseInt(cb.value));
    let csvLines = [["Nº Venta", "Cliente", "Código", "Producto", "Color", "Talle", "Cant.", "Detalles", "Nº Guía"].join(";")];

    seleccionados.forEach(idx => {
        const v = ventasData[idx];
        v.items.forEach(item => {
            let idVentaFormateado = v.venta_id ? `"\'${v.venta_id}"` : '""';
            let guiaFormateada = v.numero_guia ? `"\'${v.numero_guia}"` : '""';

            csvLines.push([
                idVentaFormateado,
                `"${v.cliente}"`,
                `"${item.sku}"`,
                `"${item.titulo}"`,
                `"${""}"`,
                `"${""}"`,
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

document.addEventListener('DOMContentLoaded', () => {
    convertirRawData();
    limpiarCarritos();
    cargarTabla();
});