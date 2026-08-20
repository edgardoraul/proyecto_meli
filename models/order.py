import json
from pathlib import Path
from typing import Any, Dict, List

# Subestados y estados reconocidos
SUBESTADOS_IMPRIMIR = {"ready_to_print"}
SUBESTADOS_IMPRESO = {"printed"}
SUBESTADOS_EN_VIAJE = {"picked_up", "authorized_by_carrier", "in_transit", "out_for_delivery"}
ESTADOS_EN_VIAJE = {"shipped"}

LOGISTICA_LOCAL = {"custom", "not_specified", "pickup", "store"}
ESTADOS_LOCAL = {"to_be_agreed"}


class OrderItem:

    def __init__(self, raw_item: Dict[str, Any]):
        item_data = raw_item.get("item", {})
        self.sku = (
            item_data.get("seller_sku")
        )
        self.title = item_data.get("title", "Sin descripción")

        variaciones = item_data.get("variation_attributes", [])
        if variaciones:
            self.variant = " - ".join(
                [
                    f"{v.get('name')}: {v.get('value_name')}"
                    for v in variaciones
                    if v.get("value_name")
                ]
            )
        else:
            self.variant = "Sin variante"

        self.quantity = raw_item.get("quantity", 1)


class Order:

    def __init__(self, raw_order: Dict[str, Any]):
        self.raw = raw_order
        self.date_created = raw_order.get("date_created", "")

        pack_id = raw_order.get("pack_id")
        order_id = raw_order.get("id")
        self.venta_id = str(pack_id) if pack_id else str(order_id or "")

        buyer = raw_order.get("buyer", {})
        nickname = buyer.get("nickname")
        nombre_completo = (
            f"{buyer.get('first_name', '')} {buyer.get('last_name', '')}".strip()
        )
        self.buyer_nickname = nickname or nombre_completo or "N/A"

        shipping_info = raw_order.get("shipping_info", {})
        shipping_raw = raw_order.get("shipping", {})

        self.tracking_number = (
            shipping_info.get("tracking_number")
            or shipping_raw.get("tracking_number")
            or "-"
        )

        self.estado_humano = self._determinar_estado_humano(
            shipping_info, shipping_raw
        )
        self.seller_note = self._extraer_notas(raw_order.get("notas_vendedor"))
        self.items: List[OrderItem] = [
            OrderItem(item) for item in raw_order.get("order_items", [])
        ]

    def _determinar_estado_humano(
        self, shipping_info: Dict[str, Any], shipping_raw: Dict[str, Any]
    ) -> str:
        substatus = shipping_info.get("substatus") or shipping_raw.get("substatus")
        status = shipping_info.get("status") or shipping_raw.get("status")
        logistic_type = shipping_info.get("logistic_type") or shipping_raw.get("logistic_type")

        if substatus in SUBESTADOS_IMPRIMIR:
            return "Imprimir rótulo"
        if substatus in SUBESTADOS_IMPRESO:
            return "Rótulo impreso"
        if substatus in SUBESTADOS_EN_VIAJE or status in ESTADOS_EN_VIAJE:
            return "En viaje"
        if logistic_type in LOGISTICA_LOCAL or status in ESTADOS_LOCAL:
            return "Retiro en Local"

        return "Retiro en Local"

    def _extraer_notas(self, notas_raw: Any) -> str:
        if not notas_raw:
            return ""

        textos = []
        items = notas_raw if isinstance(notas_raw, list) else [notas_raw]
        for n in items:
            if isinstance(n, dict):
                if n.get("note") and str(n.get("note")).strip():
                    textos.append(str(n.get("note")).strip())
                for sub in n.get("results", []):
                    if (
                        isinstance(sub, dict)
                        and sub.get("note")
                        and str(sub.get("note")).strip()
                    ):
                        textos.append(str(sub.get("note")).strip())

        return " | ".join(textos)

    @staticmethod
    def _cumple_criterio_estado(raw_order: Dict[str, Any]) -> bool:
        shipping_info = raw_order.get("shipping_info", {})
        shipping_raw = raw_order.get("shipping", {})

        status = shipping_info.get("status") or shipping_raw.get("status")
        substatus = shipping_info.get("substatus") or shipping_raw.get("substatus")
        logistic_type = shipping_info.get("logistic_type") or shipping_raw.get("logistic_type")

        # 1. Por Imprimir / Impreso
        if substatus in (SUBESTADOS_IMPRIMIR | SUBESTADOS_IMPRESO):
            return True

        # 2. En Viaje (por subestado o si el envío ya pasó a status 'shipped')
        if substatus in SUBESTADOS_EN_VIAJE or status in ESTADOS_EN_VIAJE:
            return True

        # 3. Retiro en Local / A coordinar
        if logistic_type in LOGISTICA_LOCAL or status in ESTADOS_LOCAL:
            return True

        return False

    @classmethod
    def cargar_desde_json(cls, json_path: Path) -> List["Order"]:
        """Carga el JSON descargado, filtra únicamente por los estados permitidos y ordena por fecha descendente."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        results = data.get("results", [])

        # Filtrar únicamente las órdenes válidas
        ordenes_filtradas = [
            cls(item) for item in results if cls._cumple_criterio_estado(item)
        ]

        # Ordenar por fecha de creación descendente
        ordenes_filtradas.sort(key=lambda x: x.date_created, reverse=True)
        return ordenes_filtradas