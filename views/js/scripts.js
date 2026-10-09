// ==============================================================================
// ARCHIVO: views/js/scripts.js
// DESCRIPCIÓN: Script de la interfaz web para renderizado de tabla, exportación CSV
//              y descarga directa de rótulos de envío desde la API de MeLi.
// ==============================================================================

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
        const esImpreso = (substatus === "ready_for_pickup" || substatus === "printed");
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
        // if (!esImprimir && !esImpreso && !esRetiroLocal && !esEnViaje) {
        if (!esImprimir && !esImpreso && !esRetiroLocal) {
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

        // 8.1 Extraer las notas del vendedor en las operaciones
        // 9. Extraer notas del vendedor (seller_notes)
        let notasTexto = "";
        if (Array.isArray(order.notas_vendedor)) {
            let notasArr = [];

            order.notas_vendedor.forEach(grupo => {
                if (Array.isArray(grupo.results)) {
                    grupo.results.forEach(res => {
                        if (res && res.note) {
                            notasArr.push(res.note);
                        }
                    });
                }
            });

            notasTexto = notasArr.join(", ");
        }


        // 9. Guardamos la orden lista en el arreglo final
        ventasData.push({
            venta_id: String(order.pack_id || order.id || ""),
            fecha: fecha,
            cliente: cliente,
            numero_guia: String(ship.tracking_number || ship.id || ""),
            detalles: notasTexto,
            texto_rotulo: texto_rotulo,
            estado_rotulo: estado_rotulo,
            items: items
        });
    }
}

// 10. Limpieza de datos repetidos en carritos
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

// 11. Carga del HTML de la tabla
function cargarTabla() {
    const tbody = document.getElementById('tablaVentas');
    if (!tbody) return;
    tbody.innerHTML = '';

    ventasData.forEach((v, index) => {
        let skusHtml = '';
        let titulosHtml = '';
        let variantesHtml = '';
        let cantidadesHtml = '';

        v.items.forEach(item => {
            skusHtml += `<strong>${item.sku}</strong>`;
            titulosHtml += `${item.titulo}`;
            variantesHtml += `${item.variante}`;
            cantidadesHtml += `${item.cantidad}`;
        });

        skusHtml += '';
        titulosHtml += '';
        variantesHtml += '';
        cantidadesHtml += '';

        let trClass = (index > 0 && v.venta_id !== "") ? ' class="borde-separador"' : '';

        tbody.innerHTML += `<tr${trClass}>
            <td><input type="checkbox" id="${index}" class="row-checkbox" value="${index}" onchange="actualizarBoton()"></td>
            <td><label for="${index}">${v.fecha}</label></td>
            <td><label for="${index}"><strong>${v.venta_id}</strong></label></td>
            <td class="cliente"><label for="${index}"><strong>${v.cliente}</strong></label></td>
            <td><label for="${index}">${skusHtml}</label></td>
            <td><label for="${index}">${titulosHtml}</label></td>
            <td><label for="${index}">${variantesHtml}</label></td>
            <td><label for="${index}">${cantidadesHtml}</label></td>
            <td><label for="${index}">${v.detalles || ''}</label></td>
            <td><button class="button badge-${v.estado_rotulo}" onclick="imprimirRotuloIndividual('${index}')">${v.texto_rotulo}</button></td>
        </tr>`;
    });
}

// 12. Botones de exportación del CSV
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
    const btnRots = document.getElementById('btnRots');
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

    if (btnRots) {
        btnRots.disabled = !esValido;
        btnRots.classList.toggle('active', esValido);
    }
}

// 13. Exportar el CSV
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

// 0. Carga las anteriores funciones una vez cargado el DOM.
document.addEventListener('DOMContentLoaded', () => {
    convertirRawData();
    limpiarCarritos();
    cargarTabla();
});


// ==============================================================================
// FUNCIONES DE IMPRESIÓN DIRECTA DE RÓTULOS (SIN SERVIDOR LOCAL)
// ==============================================================================
/**
 * Consulta la API oficial de Mercado Libre (/shipment_labels) conforme a
 * la documentación de Mercado Envíos 2 y descarga los rótulos en formato PDF.
 */
async function imprimirRotulos() {
    // 1. Validar presencia de TEMP_DATA y su access_token
    if (typeof TEMP_DATA === 'undefined' || !TEMP_DATA.access_token) {
        alert("❌ No se encontró el 'access_token' en TEMP_DATA.\nVerifique que Python lo haya inyectado al generar views/js/temp_data.js.");
        return;
    }

    const tokenActivo = TEMP_DATA.access_token;
    const rawOrders = Array.isArray(TEMP_DATA) ? TEMP_DATA : (TEMP_DATA.results || []);

    // 2. Obtener los índices de las filas marcadas en la tabla
    const seleccionados = Array.from(document.querySelectorAll('.row-checkbox:checked'))
        .map(cb => parseInt(cb.value));

    if (seleccionados.length === 0) {
        alert("⚠️ Seleccione al menos una venta para imprimir sus rótulos.");
        return;
    }

    // 3. Extraer el shipment_id numérico puro (shipping_info.id o shipping.id) según API MeLi
    const coleccionShipments = [];

    seleccionados.forEach(idx => {
        const venta = ventasData[idx];
        if (!venta) return;

        // Búsqueda del ID de envío interno en el JSON original
        const orderOriginal = rawOrders[idx];
        let shipmentIdReal = "";

        if (orderOriginal) {
            const shipInfo = orderOriginal.shipping_info || {};
            const shipBase = orderOriginal.shipping || {};
            shipmentIdReal = String(shipInfo.id || shipBase.id || "");
        }

        // Respaldo secundario si no se halla en orderOriginal
        if (!shipmentIdReal || shipmentIdReal === "undefined") {
            shipmentIdReal = String(venta.numero_guia || "").trim();
        }

        if (shipmentIdReal && shipmentIdReal !== "" && shipmentIdReal !== "undefined") {
            if (!coleccionShipments.includes(shipmentIdReal)) {
                coleccionShipments.push(shipmentIdReal);
            }
        }
    });

    // 4. Validaciones reglamentarias de la documentación oficial de MeLi
    if (coleccionShipments.length === 0) {
        alert("⚠️ No se encontraron IDs de envío válidos (shipment_id) en las filas seleccionadas.");
        return;
    }

    if (coleccionShipments.length > 50) {
        alert(`⚠️ Mercado Libre permite un máximo de 50 rótulos por consulta. Seleccionó ${coleccionShipments.length}.`);
        return;
    }

    console.log(`🖨️ Solicitando PDF a Mercado Libre para ${coleccionShipments.length} envío(s):`, coleccionShipments);

    // 5. Construcción de URL y Header conforme a la especificación cURL oficial:
    // GET -H 'Authorization: Bearer $ACCESS_TOKEN' https://api.mercadolibre.com/shipment_labels?shipment_ids=ID1,ID2&response_type=pdf
    const shipmentIdsParam = coleccionShipments.join(',');
    const urlApi = `https://api.mercadolibre.com/shipment_labels?shipment_ids=${shipmentIdsParam}&response_type=pdf`;

    try {
        const response = await fetch(urlApi, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${tokenActivo}`
            }
        });

        if (!response.ok) {
            const errorText = await response.text();

            // Diagnóstico explícito de error 400
            if (response.status === 400) {
                throw new Error(`Error 400 de Mercado Libre: ${errorText}\n\nVerifique:\n- Estado del envío (debe ser 'ready_to_ship' y subestado 'ready_to_print' o 'printed').\n- Tipo de logística (Fulfillment no permite imprimir etiquetas desde la API).\n- Límite máximo de 50 shipment_ids.`);
            }

            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // 6. Generar el Blob binario del PDF y abrirlo directamente en el navegador
        const blobPdf = await response.blob();
        const blobUrl = URL.createObjectURL(blobPdf);
        window.open(blobUrl, '_blank');

    } catch (error) {
        console.error("❌ Error al descargar rótulos:", error);
        alert(`❌ Error al consultar la API de Mercado Libre:\n${error.message}`);
    }
}


/**
 * Impresión individual: obtiene el shipment_id real desde TEMP_DATA para la fila
 * seleccionada y descarga su rótulo en PDF directamente desde Mercado Libre.
 */
async function imprimirRotuloIndividual(index) {
    // 1. Validar presencia de TEMP_DATA y access_token
    if (typeof TEMP_DATA === 'undefined' || !TEMP_DATA.access_token) {
        alert("❌ No se encontró el 'access_token' en TEMP_DATA.\nVerifique que Python lo haya inyectado al generar views/js/temp_data.js.");
        return;
    }

    const tokenActivo = TEMP_DATA.access_token;
    const rawOrders = Array.isArray(TEMP_DATA) ? TEMP_DATA : (TEMP_DATA.results || []);
    const orderOriginal = rawOrders[index];

    // 2. Extraer el shipment_id numérico interno de Mercado Libre
    let shipmentIdReal = "";
    if (orderOriginal) {
        const shipInfo = orderOriginal.shipping_info || {};
        const shipBase = orderOriginal.shipping || {};
        shipmentIdReal = String(shipInfo.id || shipBase.id || "");
    }

    // Respaldo secundario si no se halla en orderOriginal
    if (!shipmentIdReal || shipmentIdReal === "undefined") {
        if (ventasData[index]) {
            shipmentIdReal = String(ventasData[index].numero_guia || "").trim();
        }
    }

    if (!shipmentIdReal || shipmentIdReal === "undefined" || shipmentIdReal === "") {
        alert("⚠️ Esta orden no posee un ID de envío (shipment_id) válido para imprimir.");
        return;
    }

    console.log(`🖨️ Solicitando rótulo individual a MeLi (Envío ID: ${shipmentIdReal})...`);

    // 3. Petición GET a la API oficial de Mercado Libre
    const urlApi = `https://api.mercadolibre.com/shipment_labels?shipment_ids=${shipmentIdReal}&response_type=pdf`;

    try {
        const response = await fetch(urlApi, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${tokenActivo}`
            }
        });

        if (!response.ok) {
            const errorText = await response.text();

            if (response.status === 400) {
                throw new Error(`Error 400 de Mercado Libre: ${errorText}\n\nVerifique:\n- Que el estado del envío sea 'ready_to_ship' / 'ready_to_print' o 'printed'.\n- Que el tipo de logística permita imprimir etiquetas.`);
            }

            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // 4. Convertir respuesta a Blob PDF y abrirlo directamente en el navegador
        const blobPdf = await response.blob();
        const blobUrl = URL.createObjectURL(blobPdf);
        window.open(blobUrl, '_blank');

    } catch (error) {
        console.error("❌ Error al descargar rótulo individual:", error);
        alert(`❌ Error al descargar el rótulo individual:\n${error.message}`);
    }
}