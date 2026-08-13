"""
controllers/meli_controller.py
------------------------------
Controlador principal encargado de consultar la API de Mercado Libre,
manejar la ampliación condicional (50 -> 100), guardar el JSON crudo en data/
y procesar las órdenes filtrando estados de interés y parseando notas.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import requests

from models.order import Order

logger = logging.getLogger(__name__)


class MeLiController:

    def __init__(
        self,
        access_token: str,
        account_name: str,
        raw_json_path: str = "data/meli_orders_raw.json",
    ):
        self.access_token = access_token
        self.account_name = account_name
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        self.raw_json_path = Path(raw_json_path)

    def _obtener_ordenes_api(self, limit: int, offset: int, seller_id: str) -> List[dict]:
        """Realiza la petición paginada a la API de MeLi en orden descendente."""
        url = (
            f"https://api.mercadolibre.com/orders/search"
            f"?seller={seller_id}&order.status=paid"
            f"&sort=date_desc&limit={limit}&offset={offset}"
        )
        res = requests.get(url, headers=self.headers)
        if res.status_code != 200:
            logger.error(f"Error al obtener órdenes: {res.text}")
            return []
        return res.json().get("results", [])

    def _obtener_shipment(self, shipment_id: str) -> Optional[dict]:
        """Consulta los detalles del envío desde Mercado Libre."""
        if not shipment_id:
            return None
        url = f"https://api.mercadolibre.com/shipments/{shipment_id}"
        try:
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.warning(f"Error consultando shipment {shipment_id}: {e}")
        return None

    def _obtener_nota_orden(self, order_id: str) -> str:
        """Rastrea y parsea el campo notes/seller_note de la orden."""
        url = f"https://api.mercadolibre.com/orders/{order_id}/notes"
        try:
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                notes_data = res.json().get("results", [])
                textos = []
                for n in notes_data:
                    texto = n.get("note", {}).get("text", "") or n.get("note", "")
                    if texto and isinstance(texto, str):
                        textos.append(texto.strip())
                if textos:
                    return " | ".join(textos)
        except Exception as e:
            logger.warning(f"Error consultando notas de orden {order_id}: {e}")
        return ""

    def guardar_json_crudo(self, raw_orders: List[dict]) -> None:
        """Guarda el listado JSON crudo devuelto por Mercado Libre en la carpeta data/."""
        self.raw_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.raw_json_path, "w", encoding="utf-8") as f:
            json.dump(raw_orders, f, indent=4, ensure_ascii=False)
        logger.info(f"JSON crudo guardado correctamente en {self.raw_json_path}")

    def procesar_ventas_filtradas(self) -> List[Order]:
        """
        Descarga órdenes, evalúa ampliación a 100 si hay colecta futura,
        persiste el JSON crudo en data/ y retorna los objetos Order filtrados.
        """
        user_info = requests.get(
            "https://api.mercadolibre.com/users/me", headers=self.headers
        ).json()
        seller_id = user_info["id"]

        logger.info(f"Consultando primeras 50 órdenes recientes para [{self.account_name}]...")
        raw_orders = self._obtener_ordenes_api(limit=50, offset=0, seller_id=seller_id)

        # 1. Carga paralela de shipments iniciales para evaluar subestados (colecta futura)
        shipment_ids_iniciales = list(
            {
                str(o["shipping"]["id"])
                for o in raw_orders
                if o.get("shipping", {}).get("id")
            }
        )

        shipments_map: Dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futuros_s = {
                executor.submit(self._obtener_shipment, s_id): s_id
                for s_id in shipment_ids_iniciales
            }
            for futuro in futuros_s:
                s_id = futuros_s[futuro]
                data = futuro.result()
                if data:
                    shipments_map[s_id] = data

        # 2. Verificar si entre la orden 25 y la 50 hay colectas futuras (future_deferred)
        ampliar_a_100 = False
        rango_evaluacion = raw_orders[24:50] if len(raw_orders) >= 25 else raw_orders

        for orden_raw in rango_evaluacion:
            s_id = str(orden_raw.get("shipping", {}).get("id"))
            shipment = shipments_map.get(s_id, {})
            substatus = shipment.get("substatus", "")
            
            if substatus == "future_deferred":
                ampliar_a_100 = True
                break

        # 3. Si corresponde, descargar de la 51 a la 100
        if ampliar_a_100:
            logger.info("Detectada colecta futura (future_deferred) entre las órdenes 25-50. Ampliando a 100 órdenes...")
            segunda_tanda = self._obtener_ordenes_api(limit=50, offset=50, seller_id=seller_id)
            raw_orders.extend(segunda_tanda)

            # Cargar shipments de la segunda tanda
            shipment_ids_nuevos = list(
                {
                    str(o["shipping"]["id"])
                    for o in segunda_tanda
                    if o.get("shipping", {}).get("id") and str(o["shipping"]["id"]) not in shipments_map
                }
            )
            with ThreadPoolExecutor(max_workers=10) as executor:
                futuros_s2 = {
                    executor.submit(self._obtener_shipment, s_id): s_id
                    for s_id in shipment_ids_nuevos
                }
                for futuro in futuros_s2:
                    s_id = futuros_s2[futuro]
                    data = futuro.result()
                    if data:
                        shipments_map[s_id] = data

        # 4. Guardar JSON crudo completo descargado
        self.guardar_json_crudo(raw_orders)

        # 5. Cargar Notas en paralelo
        order_ids = [str(o["id"]) for o in raw_orders]
        notes_map: Dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futuros_n = {
                executor.submit(self._obtener_nota_orden, o_id): o_id
                for o_id in order_ids
            }
            for futuro in futuros_n:
                o_id = futuros_n[futuro]
                nota = futuro.result()
                if nota:
                    notes_map[o_id] = nota

        # 6. Parseo y Filtrado Final
        ordenes_filtradas = []

        for raw_order in raw_orders:
            order_id = str(raw_order["id"])
            shipment_id = (
                str(raw_order.get("shipping", {}).get("id"))
                if raw_order.get("shipping", {}).get("id")
                else None
            )

            shipment_data = shipments_map.get(shipment_id) if shipment_id else None

            note_text = notes_map.get(order_id, "")
            if not note_text:
                fallback_note = raw_order.get("seller_note") or raw_order.get("notes")
                if isinstance(fallback_note, str):
                    note_text = fallback_note.strip()

            orden = Order(
                raw_order=raw_order,
                shipment_data=shipment_data,
                note_text=note_text,
            )

            # Filtro: descarta colecta futura (future_deferred), entregadas, etc.
            if orden.es_estado_de_interes():
                ordenes_filtradas.append(orden)

        logger.info(
            f"Se obtuvieron {len(ordenes_filtradas)} órdenes válidas de un total de {len(raw_orders)} analizadas."
        )

        return ordenes_filtradas