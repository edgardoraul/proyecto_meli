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
    """Representa una orden de venta simplificada con mapeo de estados operativos e históricos."""

    # Estados visuales de tu interfaz
    ESTADOS_INTERES_HUMANOS = {
        "Retiro en local",
        "A coordinar con el vendedor",
        "Imprimir Rótulo",
        "Rótulo Impreso",
        "En viaje",
        "Colecta Futura" # Agregado para que se vea bien en el HTML
    }

    # Estados lógicos basados en el historial de la API (puedes agregar los que necesites)
    ESTADOS_INTERES_API = [
        {"status": "paid", "substatus": "future_deferred"},
        {"status": "ready_to_ship", "substatus": "future_deferred"},
        {"status": "ready_to_ship", "substatus": "picked_up"},
        {"status": "ready_to_ship", "substatus": "authorized_by_carrier"}
    ]

    def __init__(
        self,
        raw_order: dict,
        shipment_data: Optional[dict] = None,
        note_text: str = "",
    ):
        self.raw_order = raw_order
        self.shipment_data = shipment_data or {}
        self.id: str = str(raw_order["id"])
        self.pack_id: Optional[str] = str(raw_order.get("pack_id")) if raw_order.get("pack_id") else None
        self.venta_id: str = self.pack_id or self.id
        self.date_created: str = raw_order.get("date_created", "")

        buyer = raw_order.get("buyer", {})
        self.buyer_nickname: str = buyer.get("nickname", "Desconocido")

        self.items: List[OrderItem] = [
            OrderItem(item) for item in raw_order.get("order_items", [])
        ]

        self.shipment_id: Optional[str] = str(self.shipment_data.get("id")) if self.shipment_data.get("id") else None
        self.tracking_number: str = self.shipment_data.get("tracking_number") or "Sin Tracking"
        
        self.estado_humano: str = self._mapear_estado(raw_order, self.shipment_data)
        self.seller_note: str = note_text

    def _mapear_estado(self, raw_order: dict, shipment: dict) -> str:
        shipping_info = raw_order.get("shipping", {})

        if not shipment or not shipment.get("id"):
            shipping_mode = shipping_info.get("mode", "")
            if shipping_mode in ("custom", "not_specified"):
                return "Retiro en Local"
            return "Retiro en local"

        logistic_type = shipment.get("logistic_type", "")
        if logistic_type in ("custom", "not_specified"):
            return "Retiro en Local"

        status = shipment.get("status", "")
        substatus = shipment.get("substatus", "")
        printed = shipment.get("date_first_printed")

        if substatus == "future_deferred":
            return "Colecta Futura"

        if status == "ready_to_ship":
            if printed is not None or substatus == "printed":
                return "Rótulo Impreso"
            elif substatus == "ready_to_print":
                return "Imprimir Rótulo"
            elif substatus == "picked_up":
                return "En camino"
            elif substatus == "authorized_by_carrier":
                return "En camino"

        return "OTRO"

    def es_estado_de_interes(self) -> bool:
        """Filtra comprobando los estados de interfaz y el historial profundo de envíos."""
        # 1. Filtro rápido por interfaz (Si ya coincide con los estados normales, pasa)
        if self.estado_humano in self.ESTADOS_INTERES_HUMANOS:
            return True

        # 2. Filtro histórico (Busca en el historial de tiempo de Mercado Libre)
        if self.shipment_data:
            # ML devuelve el historial de envío bajo 'tracking' o 'status_history'
            historial = self.shipment_data.get("tracking", [])
            
            if historial:
                ultimo_evento = historial[-1] # Tomamos el último estado cronológico
                estado_actual = ultimo_evento.get("status")
                subestado_actual = ultimo_evento.get("substatus")
            else:
                estado_actual = self.shipment_data.get("status")
                subestado_actual = self.shipment_data.get("substatus")

            # Comparamos contra el array de constantes
            for estado_valido in self.ESTADOS_INTERES_API:
                if estado_valido.get("status") == estado_actual and estado_valido.get("substatus") == subestado_actual:
                    return True

        return False