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
        res = requests.get(f"{MELI_API_URL}/users/me", headers=self.headers)
        res.raise_for_status()
        return res.json()["id"]

    def _obtener_notas_orden(self, order_id: int) -> list:
        """Consulta las notas del vendedor asociadas a una orden específica."""
        url = f"{MELI_API_URL}/orders/{order_id}/notes"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else data.get("results", [])
        return []

    def descargar_ultimas_ventas(self, limite: int = 20) -> Path:
        user_id = self._obtener_user_id()
        url = f"{MELI_API_URL}/orders/search"
        params = {"seller": user_id, "sort": "date_desc", "limit": limite}

        res = requests.get(url, headers=self.headers, params=params)
        res.raise_for_status()
        data = res.json()

        # Iterar sobre las órdenes e incluir las notas correspondientes
        for orden in data.get("results", []):
            order_id = orden.get("id")
            if order_id:
                orden["notas_vendedor"] = self._obtener_notas_orden(order_id)

        nombre_archivo = f"ventas_ultimas_{self.account_name.replace(' ', '_').lower()}.json"
        archivo_destino = DATA_DIR / nombre_archivo

        with open(archivo_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        logger.info(f"JSON con últimas {limite} ventas y notas guardado en: {archivo_destino}")
        return archivo_destino