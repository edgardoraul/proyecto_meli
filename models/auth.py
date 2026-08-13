"""
models/auth.py
--------------
Gestor de autenticación basado en archivos JSON de tokens preexistentes.
"""

import json
import logging
from pathlib import Path
import requests

from config.settings import MELI_TOKEN_URL

logger = logging.getLogger(__name__)


class MeLiAuth:
    """Gestiona la lectura y renovación de tokens utilizando archivos JSON locales."""

    def __init__(self, account_config: dict):
        self.account_name = account_config["nombre"]
        self.client_id = account_config["client_id"]
        self.client_secret = account_config["client_secret"]
        self.token_file: Path = account_config["token_file"]

    def _cargar_tokens_locales(self) -> dict:
        """Carga el diccionario de tokens desde el archivo JSON si existe."""
        if self.token_file.exists():
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(
                    f"Error al leer el archivo de tokens ({self.account_name}): {e}"
                )
        return {}

    def _guardar_tokens_locales(self, tokens: dict) -> None:
        """Guarda la respuesta actualizada de tokens en el archivo JSON."""
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=4)
            logger.info(f"Tokens actualizados en [{self.token_file.name}]")
        except Exception as e:
            logger.error(
                f"Error al guardar tokens en ({self.token_file.name}): {e}"
            )

    def renovar_token(self, refresh_token: str) -> dict:
        """Utiliza el refresh_token existente para pedir un nuevo access_token."""
        logger.info(
            f"Renovando Access Token vencido para [{self.account_name}]..."
        )
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        response = requests.post(MELI_TOKEN_URL, data=payload)

        if response.status_code == 200:
            tokens = response.json()
            self._guardar_tokens_locales(tokens)
            return tokens
        else:
            msg = (
                f"No se pudo renovar el token para [{self.account_name}]. "
                f"Respuesta de API: {response.text}"
            )
            logger.error(msg)
            raise Exception(msg)

    def get_access_token(self) -> str:
        """
        Obtiene un Access Token válido.
        Lee el archivo local y, si el token expiró, lo renueva automáticamente.
        """
        tokens = self._cargar_tokens_locales()

        if not tokens or "access_token" not in tokens:
            raise FileNotFoundError(
                f"❌ No se encontró el archivo de tokens válido en: {self.token_file.resolve()}\n"
                f"Asegurate de que el archivo exista en la carpeta 'data/' con la estructura correcta."
            )

        access_token = tokens.get("access_token")

        # Validar si el token actual sigue estando activo haciendo una consulta liviana
        headers = {"Authorization": f"Bearer {access_token}"}
        res = requests.get(
            "https://api.mercadolibre.com/users/me", headers=headers
        )

        # Si responde 401 Unauthorized, renovamos con el refresh_token
        if res.status_code == 401:
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                raise ValueError(
                    f"El access_token venció y no hay 'refresh_token' en {self.token_file.name}"
                )

            nuevos_tokens = self.renovar_token(refresh_token)
            access_token = nuevos_tokens.get("access_token")

        return access_token