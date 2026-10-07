import logging
import requests
from config.settings import COEF_PRE, COSTO_FIJO, MELI_API_URL

logger = logging.getLogger("Pricer")


def obtener_sku_articulo(item: dict) -> str:
    sku = item.get("seller_custom_field")
    if sku and str(sku).strip():
        return str(sku).strip().upper()

    for attr in item.get("attributes", []):
        if attr.get("id") in ("SELLER_SKU", "SKU") and attr.get("value_name"):
            return str(attr.get("value_name")).strip().upper()

    for var in item.get("variations", []):
        v_sku = var.get("seller_custom_field")
        if v_sku and str(v_sku).strip():
            return str(v_sku).strip().upper()
        for attr in var.get("attributes", []):
            if attr.get("id") in ("SELLER_SKU", "SKU") and attr.get("value_name"):
                return str(attr.get("value_name")).strip().upper()

    return ""

def actualizar_precios_cuenta(
    cuenta_config: dict, detalles_items: list, mapa_precios: dict, headers: dict
) -> dict:
    actualizados = 0
    omitidos_sin_sku = 0
    omitidos_bloqueados = 0
    sin_cambio = 0

    for item in detalles_items:
        item_id = item.get("id")
        listing_type_id = item.get("listing_type_id")
        precio_actual = float(item.get("price", 0.0))

        # 1. Solo publicaciones Premium
        if listing_type_id != "gold_pro":
            continue

        # 2. Obtener SKU de 7 caracteres
        sku_raw = obtener_sku_articulo(item)
        sku_7 = sku_raw[:7]

        if not sku_7 or sku_7 not in mapa_precios:
            logger.warning(
                f"⚠️ [{item_id}] SKU (7 carac): '{sku_7}' (Raw: '{sku_raw}') no encontrado en la planilla CSV."
            )
            omitidos_sin_sku += 1
            continue

        # 3. Calcular precio
        precio_base = mapa_precios[sku_7]
        precio_calculado = round(precio_base * COEF_PRE + COSTO_FIJO, 0)

        # 4. Omitir si el precio es idéntico
        if precio_actual == precio_calculado:
            sin_cambio += 1
            continue

        # 5. Endpoint PUT de Mercado Libre
        url_update = f"{MELI_API_URL}/items/{item_id}"

        variations = item.get("variations", [])
        if variations:
            payload = {
                "variations": [
                    {"id": v["id"], "price": precio_calculado}
                    for v in variations
                ]
            }
        else:
            payload = {"price": precio_calculado}

        try:
            res_upd = requests.put(
                url_update, headers=headers, json=payload, timeout=10
            )

            if res_upd.status_code == 200:
                logger.info(
                    f"✅ [{item_id}] SKU: {sku_7} | Precio actualizado: ${precio_actual:,.2f} -> ${precio_calculado:,.2f}"
                )
                actualizados += 1
            else:
                err_text = res_upd.text
                if (
                    "item.price.not_modifiable" in err_text
                    or "has_bids" in err_text
                    or "promotion" in err_text
                ):
                    logger.warning(
                        f"⚠️ [{item_id}] SKU: {sku_7} | Omitido: Precio bloqueado por MeLi (Promoción/Oferta activa)."
                    )
                    omitidos_bloqueados += 1
                else:
                    logger.error(
                        f"❌ [{item_id}] Error HTTP {res_upd.status_code} al actualizar: {err_text}"
                    )
        except Exception as e:
            logger.error(f"❌ [{item_id}] Excepción al actualizar precio: {e}")

    logger.info(
        f"📊 Resumen [{cuenta_config['nombre']}]: "
        f"{actualizados} actualizados | {sin_cambio} sin cambios | "
        f"{omitidos_sin_sku} sin SKU en CSV | {omitidos_bloqueados} bloqueados por oferta."
    )

    return {
        "actualizados": actualizados,
        "sin_cambio": sin_cambio,
        "omitidos_sin_sku": omitidos_sin_sku,
        "omitidos_bloqueados": omitidos_bloqueados,
    }