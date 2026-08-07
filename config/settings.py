"""
config/settings.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MELI_API_URL = "https://api.mercadolibre.com"
MELI_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REDIRECT_URI = "https://www.google.com"

CUENTAS = {}

for i in range(1, 4):
    client_id = os.getenv(f"MELI_C{i}_CLIENT_ID")
    client_secret = os.getenv(f"MELI_C{i}_CLIENT_SECRET")
    nombre = os.getenv(f"MELI_C{i}_NOMBRE", f"Cuenta {i}")

    # Lee si la cuenta usa PKCE (por defecto True)
    usa_pkce_str = os.getenv(f"MELI_C{i}_USA_PKCE", "true").lower()
    usa_pkce = usa_pkce_str in ("true", "1", "yes")

    if client_id and client_secret:
        CUENTAS[str(i)] = {
            "nombre": nombre,
            "client_id": client_id,
            "client_secret": client_secret,
            "usa_pkce": usa_pkce,
            "token_file": DATA_DIR / f"tokens_cuenta_{i}.json",
        }