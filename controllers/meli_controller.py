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
        res = requests.get(f"{MELI_API_URL}/users/me", headers=self.headers)
        res.raise_for_status()
        user_id = res.json()["id"]
        print(f"  └─ ID de usuario obtenido: {user_id}")
        return user_id

    def _obtener_notas_orden(self, order_id: int) -> list:
        url = f"{MELI_API_URL}/orders/{order_id}/notes"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else data.get("results", [])
        return []

    def descargar_ultimas_ventas(self, limite: int = 20) -> Path:
        print(f"\n🚀 Iniciando descarga para la cuenta [{self.account_name}]")
        
        user_id = self._obtener_user_id()
        
        print(f"  ├─ [2/4] Solicitando las últimas {limite} ventas a Mercado Libre...")
        url = f"{MELI_API_URL}/orders/search"
        params = {"seller": user_id, "sort": "date_desc", "limit": limite}

        res = requests.get(url, headers=self.headers, params=params)
        res.raise_for_status()
        data = res.json()
        
        ordenes = data.get("results", [])
        total_ordenes = len(ordenes)
        print(f"  └─ Se obtuvieron {total_ordenes} ventas.")

        print(f"  ├─ [3/4] Obteniendo notas del vendedor para cada orden...")
        for idx, orden in enumerate(ordenes, start=1):
            order_id = orden.get("id")
            pack_id = orden.get("pack_id")

            if order_id:
                identificador = f"Pack ID: {pack_id}" if pack_id else f"Orden ID: {order_id}"
                print(f"     ├─ [{idx}/{total_ordenes}] Descargando notas de {identificador}")
                notas = self._obtener_notas_orden(order_id)
                orden["notas_vendedor"] = notas
                print(f"     │  └─ Se encontraron {len(notas)} nota(s).")

        nombre_archivo = f"ventas_ultimas_{self.account_name.replace(' ', '_').lower()}.json"
        archivo_destino = DATA_DIR / nombre_archivo

        print(f"  ├─ [4/4] Guardando datos en archivo JSON: {archivo_destino.name}")
        with open(archivo_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"  └─ ✔ ¡Proceso finalizado! Archivo guardado correctamente en: {archivo_destino}\n")
        logger.info(f"JSON con últimas {limite} ventas y notas guardado en: {archivo_destino}")
        return archivo_destino