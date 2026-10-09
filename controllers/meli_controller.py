# ==============================================================================
# ARCHIVO: controllers/meli_controller.py
# DESCRIPCIÓN: Controlador para la descarga de órdenes/ventas recientes,
#              notas de vendedor e información logística desde la API de MeLi,
#              exportando los datos y credenciales en JSON y JS temporal.
# ==============================================================================

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import requests
from config.settings import DATA_DIR, MELI_API_URL

logger = logging.getLogger(__name__)


class MeLiController:
    """
    Gestiona la interacción con la API de Mercado Libre para consultar
    las ventas recientes, enriquecerlas con datos de envío/notas e inyectar
    el token activo en el archivo JS temporal de la vista.
    """

    def __init__(self, access_token: str, account_name: str):
        """
        Inicializa el controlador guardando el token activo de la cuenta
        (leído previamente desde data/tokens_cuenta_xx.json).
        """
        self.access_token = access_token
        self.account_name = account_name
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def _obtener_user_id(self) -> int:
        """Obtiene el ID numérico del usuario vendedor autenticado."""
        print("  ├─ [1/4] Obteniendo ID del usuario vendedor...")
        res = requests.get(f"{MELI_API_URL}/users/me", headers=self.headers, timeout=10)
        res.raise_for_status()
        user_id = res.json()["id"]
        print(f"  └─ ID de usuario obtenido: {user_id}")
        return user_id

    def _obtener_notas_orden(self, order_id: int) -> list:
        """Consulta las notas internas creadas por el vendedor para una orden."""
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
        """Obtiene el detalle completo del envío (substatus, tipo logístico, tracking, etc.)."""
        url = f"{MELI_API_URL}/shipments/{shipping_id}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.warning(f"Error al obtener shipping info {shipping_id}: {e}")
        return {}

    def _procesar_orden(self, item: tuple) -> str:
        """Procesa de forma independiente el envío y las notas de una orden (ejecutado en hilo)."""
        idx, orden, total = item
        order_id = orden.get("id")
        pack_id = orden.get("pack_id")

        if not order_id:
            return ""

        identificador = f"Pack ID: {pack_id}" if pack_id else f"Orden ID: {order_id}"

        # 1. Obtener datos de envío
        shipping = orden.get("shipping", {})
        shipping_id = shipping.get("id") if isinstance(shipping, dict) else None
        if shipping_id:
            orden["shipping_info"] = self._obtener_shipping_info(shipping_id)

        # 2. Obtener notas del vendedor
        notas = self._obtener_notas_orden(order_id)
        orden["notas_vendedor"] = notas

        return f"    ├─ [{idx}/{total}] Procesado {identificador} (Notas: {len(notas)})"

    def descargar_ultimas_ventas(self, limite: int = 20, max_workers: int = 50) -> Path:
        """
        Descarga las últimas órdenes registradas, enriquece los datos en paralelo,
        guarda el JSON de respaldo e inyecta 'access_token' y 'results' en 'views/js/temp_data.js'.
        """
        print(f"\n🚀 Iniciando descarga para la cuenta [{self.account_name}]")
        
        user_id = self._obtener_user_id()
        
        print(f"  ├─ [2/4] Solicitando las últimas {limite} ventas a Mercado Libre...")
        url = f"{MELI_API_URL}/orders/search"
        
        ordenes = []
        offset = 0
        TAMANO_PAGINA = 20  # Lotes de 20 en 20

        while len(ordenes) < limite:
            cuantos_pedir = min(TAMANO_PAGINA, limite - len(ordenes))
            params = {
                "seller": user_id,
                "sort": "date_desc",
                "limit": cuantos_pedir,
                "offset": offset,
            }

            res = requests.get(url, headers=self.headers, params=params, timeout=10)
            res.raise_for_status()
            data_page = res.json()

            batch = data_page.get("results", [])
            if not batch:
                break

            ordenes.extend(batch)
            offset += len(batch)
            
            print(f"    ├─ Descargadas {len(ordenes)} de {limite} (offset: {offset})")

            if len(batch) < cuantos_pedir:
                break

        total_ordenes = len(ordenes)
        print(f"  └─ Se obtuvieron {total_ordenes} ventas.")

        print(f"  ├─ [3/4] Obteniendo envíos y notas en paralelo ({max_workers} hilos)...")
        
        tareas = [(idx, orden, total_ordenes) for idx, orden in enumerate(ordenes, start=1)]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._procesar_orden, tarea) for tarea in tareas]
            for future in as_completed(futures):
                msg = future.result()
                if msg:
                    print(msg)

        nombre_archivo = f"ventas_ultimas_{self.account_name.replace(' ', '_').lower()}.json"
        archivo_destino = DATA_DIR / nombre_archivo

        print("  ├─ [4/4] Guardando datos en archivo JSON y JS...")

        # INYECCIÓN DEL ACCESS TOKEN: Se agrega el token al diccionario que lee el JS
        data_final = {
            "account": self.account_name,
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "user_id": self.user_id,
            "refresh_token": self.refresh_token,
            "results": ordenes
        }

        # 1. Guardar JSON original de respaldo
        with open(archivo_destino, "w", encoding="utf-8") as f:
            json.dump(data_final, f, indent=4, ensure_ascii=False)

        # 2. Guardar temp_data.js en views/js/
        archivo_js = Path("views/js/temp_data.js")
        archivo_js.parent.mkdir(parents=True, exist_ok=True)

        json_str = json.dumps(data_final, ensure_ascii=False, indent=4)
        with open(archivo_js, "w", encoding="utf-8") as f:
            f.write(f"const TEMP_DATA = {json_str};\n")

        print("  └─ ✔ ¡Proceso finalizado!")
        print(f"     - JSON: {archivo_destino}")
        print(f"     - JS:   {archivo_js}\n")
        
        logger.info(f"Archivos guardados en: {archivo_destino} y {archivo_js}")
        return archivo_destino