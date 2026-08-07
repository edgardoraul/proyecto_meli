"""
config/settings.py
------------------
Carga de forma segura las credenciales desde variables de entorno (.env).
Evita exponer credenciales o tokens en repositorios públicos/privados.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Rutas absolutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Crear directorio de datos/tokens si no existe
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cargar variables del archivo .env (busca en la raíz del proyecto)
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Endpoints globales de Mercado Libre
MELI_API_URL = "https://api.mercadolibre.com"
MELI_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REDIRECT_URI = "https://www.google.com"

# Mapeo de cuentas dinámico desde el archivo .env
CUENTAS = {}

# Leemos hasta 3 cuentas (o las que estén configuradas en el .env)
for i in range(1, 4):
    client_id = os.getenv(f"MELI_C{i}_CLIENT_ID")
    client_secret = os.getenv(f"MELI_C{i}_CLIENT_SECRET")
    nombre = os.getenv(f"MELI_C{i}_NOMBRE", f"Cuenta {i}")

    # Solo agregamos la cuenta si tiene credenciales válidas en el .env
    if client_id and client_secret:
        CUENTAS[str(i)] = {
            "nombre": nombre,
            "client_id": client_id,
            "client_secret": client_secret,
            # Los tokens se guardan en el directorio data/ local, que está en el .gitignore
            "token_file": DATA_DIR / f"tokens_cuenta_{i}.json"
        }