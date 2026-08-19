from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import requests
from config.settings import DATA_DIR, MELI_API_URL

logger = logging.getLogger(__name__)


class MeLiController:

    def __init__(self, access_token: str, account_name: str):
        self.access_token = access_token
        self.account_name = account_name
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def _obtener_user_id(self) -> int:
        print("  ├─ [1/4] Obteniendo ID del usuario vendedor...")
        res = requests.get(f"{MELI_API_URL}/users/me", headers=self.headers, timeout=10)
        res.raise_for_status()
        user_id = res.json()["id"]
        print(f"  └─ ID de usuario obtenido: {user_id}")
        return user_id

    def _obtener_notas_orden(self, order_id: int) -> list:
        url = f"{MELI_API_URL}/orders/{order_id}/notes"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data if isinstance(data, list) else data.get("results", [])
        except Exception as e:
            logger.warning(f"Error al obtener notas de orden {order_id}: {e}")
        return []

    def _obtener_shipping_info(self, shipping_id: int) -> dict:
        url = f"{MELI_API_URL}/shipments/{shipping_id}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.warning(f"Error al obtener shipping info {shipping_id}: {e}")
        return {}

    def _procesar_orden(self, item: tuple) -> str:
        """Procesa de forma independiente el envío y las notas de una orden."""
        idx, orden, total = item
        order_id = orden.get("id")
        pack_id = orden.get("pack_id")

        if not order_id:
            return ""

        identificador = f"Pack ID: {pack_id}" if pack_id else f"Orden ID: {order_id}"

        # 1. Obtener envío
        shipping = orden.get("shipping", {})
        shipping_id = shipping.get("id") if isinstance(shipping, dict) else None
        if shipping_id:
            orden["shipping_info"] = self._obtener_shipping_info(shipping_id)

        # 2. Obtener notas
        notas = self._obtener_notas_orden(order_id)
        orden["notas_vendedor"] = notas

        return f"     ├─ [{idx}/{total}] Procesado {identificador} (Notas: {len(notas)})"

    def descargar_ultimas_ventas(self, limite: int = 20, max_workers: int = 10) -> Path:
        print(f"\n🚀 Iniciando descarga para la cuenta [{self.account_name}]")
        
        user_id = self._obtener_user_id()
        
        print(f"  ├─ [2/4] Solicitando las últimas {limite} ventas a Mercado Libre...")
        url = f"{MELI_API_URL}/orders/search"
        params = {"seller": user_id, "sort": "date_desc", "limit": limite}

        res = requests.get(url, headers=self.headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        ordenes = data.get("results", [])
        total_ordenes = len(ordenes)
        print(f"  └─ Se obtuvieron {total_ordenes} ventas.")

        print(f"  ├─ [3/4] Obteniendo envíos y notas en paralelo ({max_workers} hilos)...")
        
        # Crear lista de tareas
        tareas = [(idx, orden, total_ordenes) for idx, orden in enumerate(ordenes, start=1)]

        # Ejecución en paralelo
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._procesar_orden, tarea) for tarea in tareas]
            for future in as_completed(futures):
                msg = future.result()
                if msg:
                    print(msg)

        nombre_archivo = f"ventas_ultimas_{self.account_name.replace(' ', '_').lower()}.json"
        archivo_destino = DATA_DIR / nombre_archivo

        print(f"  ├─ [4/4] Guardando datos en archivo JSON: {archivo_destino.name}")
        with open(archivo_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"  └─ ✔ ¡Proceso finalizado! Archivo guardado correctamente en: {archivo_destino}\n")
        logger.info(f"JSON con últimas {limite} ventas guardado en: {archivo_destino}")
        return archivo_destino