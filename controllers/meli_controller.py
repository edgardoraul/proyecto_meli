"""
controllers/meli_controller.py
------------------------------
Controlador principal encargada de consultar la API con paginación,
asociar envíos/notas en paralelo y filtrar solo las ventas de interés.
"""

import logging
from typing import List
import requests

from models.order import Order

logger = logging.getLogger(__name__)


class MeLiController:

    def __init__(self, access_token: str, account_name: str):
        self.access_token = access_token
        self.account_name = account_name
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def obtener_todas_las_ordenes_recientes(
        self, limite_total: int = 50
    ) -> List[dict]:
        """
        Obtiene las órdenes más recientes del vendedor aplicando paginación
        para superar el límite de 50 por consulta que impone Mercado Libre.
        """
        user_info = requests.get(
            "https://api.mercadolibre.com/users/me", headers=self.headers
        ).json()
        seller_id = user_info["id"]

        todas_las_ordenes = []
        offset = 0
        limit_por_pagina = 50

        logger.info(
            f"Buscando hasta {limite_total} órdenes recientes para [{self.account_name}]..."
        )

        while len(todas_las_ordenes) < limite_total:
            # Petición paginada en orden descendente
            url = (
                f"https://api.mercadolibre.com/orders/search"
                f"?seller={seller_id}&order.status=paid"
                f"&sort=date_desc&limit={limit_por_pagina}&offset={offset}"
            )

            res = requests.get(url, headers=self.headers)
            if res.status_code != 200:
                logger.error(f"Error al obtener órdenes: {res.text}")
                break

            results = res.json().get("results", [])
            if not results:
                break  # No hay más órdenes disponibles

            todas_las_ordenes.extend(results)
            offset += limit_por_pagina

            logger.info(
                f"Descargadas {len(todas_las_ordenes)} órdenes acumuladas..."
            )

            # Si trajimos menos de 50, llegamos al final de las ventas disponibles
            if len(results) < limit_por_pagina:
                break

        # Nos aseguramos de devolver solo hasta el límite deseado
        return todas_las_ordenes[:limite_total]

    def procesar_ventas_filtradas(self, limite_peticion: int = 50) -> List[Order]:
        """
        Descarga, mapea y filtra las ventas conservando ÚNICAMENTE
        las que están en estados de interés.
        """
        raw_orders = self.obtener_todas_las_ordenes_recientes(
            limite_total=limite_peticion
        )

        # Aquí integrarás las llamadas a shipments y notas de tu lógica existente
        # (vía requests o aiohttp en paralelo para que sea ultra rápido)
        shipments_map = {}  # {shipment_id: datos_shipment}
        notes_map = {}  # {order_id: nota_texto}

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

            # Creamos el objeto usando el modelo
            orden = Order(
                raw_order=raw_order,
                shipment_data=shipment_data,
                note_text=note_text,
            )

            # FILTRO: Solo agregamos la orden si está en los 4 estados que te interesan
            if orden.es_estado_de_interes():
                ordenes_filtradas.append(orden)

        logger.info(
            f"Se obtuvieron {len(ordenes_filtradas)} órdenes útiles de un total de {len(raw_orders)} analizadas."
        )

        # Retornamos ordenadas en forma descendente por fecha/id (ya vienen ordenadas de la API por date_desc)
        return ordenes_filtradas