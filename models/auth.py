"""
models/auth.py
--------------
Modelo de Autenticación compatible tanto con aplicaciones modernas (PKCE)
como con aplicaciones antiguas/legacy (OAuth 2.0 estándar).
"""

import base64
import hashlib
import json
import logging
import secrets
import webbrowser
from pathlib import Path
import requests

from config.settings import MELI_AUTH_URL, MELI_TOKEN_URL, REDIRECT_URI

logger = logging.getLogger(__name__)


class MeLiAuth:
    """Gestiona la autenticación OAuth 2.0 (con o sin PKCE) por cuenta."""

    def __init__(self, account_config: dict):
        self.account_name = account_config["nombre"]
        self.client_id = account_config["client_id"]
        self.client_secret = account_config["client_secret"]
        self.usa_pkce: bool = account_config.get("usa_pkce", True)
        self.token_file: Path = account_config["token_file"]

    def _generar_pkce(self) -> tuple[str, str]:
        """Genera el Code Verifier y Code Challenge para PKCE."""
        verifier = secrets.token_urlsafe(64)[:128]
        hashed = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = (
            base64.urlsafe_b64encode(hashed).decode("utf-8").replace("=", "")
        )
        return verifier, challenge

    def _cargar_tokens_locales(self) -> dict:
        if self.token_file.exists():
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(
                    f"Error al leer tokens locales ({self.account_name}): {e}"
                )
        return {}

    def _guardar_tokens_locales(self, tokens: dict) -> None:
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=4)
            logger.info(
                f"Tokens guardados exitosamente para [{self.account_name}]"
            )
        except Exception as e:
            logger.error(
                f"Error al guardar tokens locales ({self.account_name}): {e}"
            )

    def autenticar_primer_uso(self) -> dict:
        """Inicia el flujo interactivo según la modalidad de la app (PKCE vs Estándar)."""
        verifier = None

        # 1. Armado de la URL de Autorización
        auth_url = (
            f"{MELI_AUTH_URL}?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={REDIRECT_URI}"
        )

        # Si la cuenta requiere PKCE, agregamos el desafío a la URL
        if self.usa_pkce:
            verifier, challenge = self._generar_pkce()
            auth_url += (
                f"&code_challenge={challenge}&code_challenge_method=S256"
            )
            logger.info(
                f"Modo de autenticación: OAuth 2.0 + PKCE para [{self.account_name}]"
            )
        else:
            logger.info(
                f"Modo de autenticación: OAuth 2.0 Estándar (Legacy) para [{self.account_name}]"
            )

        print(f"\n==================================================")
        print(f" AUTENTICACIÓN REQUERIDA: {self.account_name}")
        print(
            f" Modo: {'PKCE' if self.usa_pkce else 'Estándar (App Antigua)'}"
        )
        print(f"==================================================")
        print(f"1. Se abrirá la siguiente URL en tu navegador:\n{auth_url}\n")

        webbrowser.open(auth_url)
        code = input("2. Pegá el código de autorización (TG-...): ").strip()

        # 2. Armado del Payload para solicitar Tokens
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }

        # Solo enviamos code_verifier si la cuenta usa PKCE
        if self.usa_pkce and verifier:
            payload["code_verifier"] = verifier

        response = requests.post(MELI_TOKEN_URL, data=payload)
        if response.status_code == 200:
            tokens = response.json()
            self._guardar_tokens_locales(tokens)
            return tokens
        else:
            msg = f"Error al autenticar [{self.account_name}]: {response.text}"
            logger.error(msg)
            raise Exception(msg)

    def renovar_token(self, refresh_token: str) -> dict:
        """Renueva el token (el refresco funciona igual para ambos tipos de app)."""
        logger.info(f"Renovando Access Token para [{self.account_name}]...")
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
            logger.warning(
                f"Refresh Token expirado para [{self.account_name}]. Reautenticando..."
            )
            return self.autenticar_primer_uso()

    def get_access_token(self) -> str:
        """Devuelve un Access Token válido, renovándolo automáticamente si venció."""
        tokens = self._cargar_tokens_locales()
        if not tokens or "access_token" not in tokens:
            tokens = self.autenticar_primer_uso()

        access_token = tokens.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}

        res = requests.get(
            "https://api.mercadolibre.com/users/me", headers=headers
        )

        if res.status_code == 401:
            tokens = self.renovar_token(tokens.get("refresh_token", ""))
            access_token = tokens.get("access_token")

        return access_token