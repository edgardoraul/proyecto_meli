"""
models/order.py
---------------
Clases de dominio para representar Ítems y Órdenes de Mercado Libre.
"""

from typing import List, Optional


class OrderItem:
    """Representa un ítem dentro de una orden (sin información monetaria)."""

    def __init__(self, raw_item_data: dict):
        item_info = raw_item_data.get("item", {})

        self.id: str = item_info.get("id", "")
        self.title: str = item_info.get("title", "")
        self.sku: str = item_info.get("seller_sku") or "SIN SKU"
        self.quantity: int = raw_item_data.get("quantity", 0)

        # Parseo de variaciones (Ej: Color: Negro, Talle: Único)
        variations = item_info.get("variation_attributes", [])
        if variations:
            self.variant = ", ".join(
                [
                    f"{v.get('name')}: {v.get('value_name')}"
                    for v in variations
                    if v.get("name") and v.get("value_name")
                ]
            )
        else:
            self.variant = "Sin variante"


class Order:
    """Representa una orden de venta simplificada con mapeo de estados operativos."""

    ESTADOS_INTERES = {
        "Retiro en local",
        "A coordinar con el vendedor",
        "Imprimir Rótulo",
        "Rótulo Impreso",
    }

    def __init__(
        self,
        raw_order: dict,
        shipment_data: Optional[dict] = None,
        note_text: str = "",
    ):
        # 1. Identificadores y Fechas
        self.id: str = str(raw_order["id"])
        self.pack_id: Optional[str] = (
            str(raw_order.get("pack_id")) if raw_order.get("pack_id") else None
        )
        self.venta_id: str = self.pack_id or self.id
        self.date_created: str = raw_order.get("date_created", "")

        # 2. Cliente (Únicamente Nickname/Usuario)
        buyer = raw_order["buyer"]
        self.buyer_nickname: str = buyer["nickname"]

        # 3. Ítems
        self.items: List[OrderItem] = [
            OrderItem(item) for item in raw_order.get("order_items", [])
        ]

        # 4. Datos de Envío
        shipment = shipment_data or {}
        self.shipment_id: Optional[str] = (
            str(shipment.get("id")) if shipment.get("id") else None
        )
        self.tracking_number: str = (
            shipment.get("tracking_number") or "Sin Tracking"
        )

        # 5. Estado Interno
        self.estado_humano: str = self._mapear_estado(raw_order, shipment)

        # 6. Notas del Vendedor
        self.seller_note: str = note_text

    def _mapear_estado(self, raw_order: dict, shipment: dict) -> str:
        shipping_info = raw_order.get("shipping", {})

        if not shipment or not shipment.get("id"):
            shipping_mode = shipping_info.get("mode", "")
            if shipping_mode in ("custom", "not_specified"):
                return "A coordinar con el vendedor"
            return "Retiro en local"

        logistic_type = shipment.get("logistic_type", "")
        if logistic_type in ("custom", "not_specified"):
            return "A coordinar con el vendedor"

        status = shipment.get("status", "")
        substatus = shipment.get("substatus", "")
        printed = shipment.get("date_first_printed")

        if status == "ready_to_ship":
            if printed is not None or substatus == "printed":
                return "Rótulo Impreso"
            elif substatus == "ready_to_print":
                return "Imprimir Rótulo"

        return "OTRO"

    def es_estado_de_interes(self) -> bool:
        return self.estado_humano in self.ESTADOS_INTERES