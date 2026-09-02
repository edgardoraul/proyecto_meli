let ventasData = [];

// Convierte TEMP_DATA (JSON crudo) al formato estructurado para la tabla
function convertirRawData() {
    // 1. Validar que exista la información
    if (typeof TEMP_DATA === 'undefined') {
        console.error("❌ No se encontró TEMP_DATA");
        return;
    }

    const rawOrders = Array.isArray(TEMP_DATA) ? TEMP_DATA : (TEMP_DATA.results || []);

    // 2. Recorremos cada orden recibida
    for (const order of rawOrders) {
        // Evitamos errores si no existe shipping_info
        const ship = order.shipping_info || "";
        const substatus = ship.substatus || "";
        const status = ship.status || order.status || "";
        const logisticType = ship.logistic_type || "";

        // 3. Evaluamos a qué grupo pertenece la orden
        const esImprimir = (substatus === "ready_to_print");
        const esImpreso = (substatus === "printed" || status === "ready_to_ship");
        const esRetiroLocal = (
            logisticType == "custom" ||
            logisticType == "not_specified" ||
            logisticType == "pickup" ||
            logisticType == "store" ||
            status == "to_be_agreed"
        );
        const esEnViaje = (
            substatus == "picked_up" ||
            substatus == "authorized_by_carrier" ||
            substatus == "in_transit" ||
            substatus == "out_for_delivery" ||
            status == "shipped"
        );

        // 4. SI NO ES DE NINGUNO DE ESTOS GRUPOS, LA SALTAMOS (NO SE MOSTRARÁ)
        if (!esImprimir && !esImpreso && !esRetiroLocal && !esEnViaje) {
            continue; // Salta a la siguiente orden
        }

        // 5. Asignamos textos y colores según el grupo
        let texto_rotulo = "";
        let estado_rotulo = "";

        if (esImprimir) {
            texto_rotulo = "Imprimir rótulo";
            estado_rotulo = "Verde";
        } else if (esImpreso) {
            texto_rotulo = "Rótulo impreso";
            estado_rotulo = "Naranja";
        } else if (esRetiroLocal) {
            texto_rotulo = "Retiro en Local";
            estado_rotulo = "NaranjaClaro";
        } else if (esEnViaje) {
            texto_rotulo = "En viaje";
            estado_rotulo = "Gris";
        }

        // 6. Formateamos la fecha (DD/MM/YYYY)
        const dateObj = new Date(order.date_created);
        let fecha = "";
        if (!isNaN(dateObj)) {
            fecha = dateObj.toLocaleDateString('es-AR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        }

        // 7. Obtenemos cliente (con respaldo si falla)
        const buyer = order.buyer || {};
        const cliente = buyer.nickname || `${buyer.first_name || ''} ${buyer.last_name || ''}`.trim() || "Cliente MeLi";

        // 8. Armamos la lista de productos
        const items = [];
        const rawItems = order.order_items || [];

        for (const oi of rawItems) {
            const item = oi.item || {};

            // Manejo de variantes (color, talle, etc.)
            let variante = "-";
            if (item.variation_attributes && item.variation_attributes.length > 0) {
                const listaVariantes = [];
                for (const attr of item.variation_attributes) {
                    listaVariantes.push(`${attr.name}: ${attr.value_name}`);
                }
                variante = listaVariantes.join(", ");
            }

            items.push({
                sku: item.seller_sku || item.seller_custom_field || item.id || "-",
                titulo: item.title || "",
                variante: variante,
                cantidad: oi.quantity || 1
            });
        }

        // 9. Guardamos la orden lista en el arreglo final
        ventasData.push({
            venta_id: String(order.pack_id || order.id || ""),
            fecha: fecha,
            cliente: cliente,
            numero_guia: String(ship.tracking_number || ship.id || ""),
            detalles: order.notes || "",
            texto_rotulo: texto_rotulo,
            estado_rotulo: estado_rotulo,
            items: items
        });
    }
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
            <td><input type="checkbox" id="${v.venta_id}" class="row-checkbox" value="${index}" onchange="actualizarBoton()"></td>
            <td><label for="${v.venta_id}">${v.fecha}</label></td>
            <td style="background-color:#eee;"><label for="${v.venta_id}"><strong>${v.venta_id}</strong></label></td>
            <td><label for="${v.venta_id}"><strong>${v.cliente}</strong></label></td>
            <td><label for="${v.venta_id}">${skusHtml}</label></td>
            <td><label for="${v.venta_id}">${titulosHtml}</label></td>
            <td><label for="${v.venta_id}">${variantesHtml}</label></td>
            <td><label for="${v.venta_id}">${cantidadesHtml}</label></td>
            <td><label for="${v.venta_id}">${v.detalles || ''}</label></td>
            <td><label for="${v.venta_id}"><span class="badge badge-${v.estado_rotulo}">${v.texto_rotulo}</span></label></td>
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