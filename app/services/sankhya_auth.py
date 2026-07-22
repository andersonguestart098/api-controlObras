import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import SankhyaAuthenticationError


class SankhyaAuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_token: str | None = None
        self._token_expiration: datetime | None = None
        self._refresh_lock = asyncio.Lock()

    @property
    def token_expiration(self) -> datetime | None:
        return self._token_expiration

    def token_is_valid(self) -> bool:
        if not self._access_token or not self._token_expiration:
            return False
        safety_margin = timedelta(seconds=60)
        return datetime.now(timezone.utc) < self._token_expiration - safety_margin

    async def get_token(self) -> str:
        if self.token_is_valid() and self._access_token:
            return self._access_token
        return await self.refresh_token()

    async def refresh_token(self) -> str:
        async with self._refresh_lock:
            if self.token_is_valid() and self._access_token:
                return self._access_token

            headers = {
                "X-Token": self._settings.sankhya_x_token,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            data = {
                "grant_type": "client_credentials",
                "client_id": self._settings.sankhya_client_id,
                "client_secret": self._settings.sankhya_client_secret,
            }

            try:
                async with httpx.AsyncClient(timeout=self._settings.sankhya_timeout_seconds) as client:
                    response = await client.post(
                        self._settings.sankhya_auth_url,
                        headers=headers,
                        data=data,
                    )
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise SankhyaAuthenticationError(
                    f"Falha ao autenticar no Sankhya. HTTP {exc.response.status_code}."
                ) from exc
            except httpx.RequestError as exc:
                raise SankhyaAuthenticationError(
                    "Não foi possível conectar ao serviço de autenticação do Sankhya."
                ) from exc

            payload: dict[str, Any] = response.json()
            access_token = payload.get("access_token")
            if not access_token:
                raise SankhyaAuthenticationError("O Sankhya não retornou access_token.")

            try:
                expires_in = int(payload.get("expires_in", 300))
            except (TypeError, ValueError):
                expires_in = 300

            self._access_token = access_token
            self._token_expiration = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            return access_token


_auth_service: SankhyaAuthService | None = None


def get_sankhya_auth_service(
    settings: Settings = Depends(get_settings),
) -> SankhyaAuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = SankhyaAuthService(settings)
    return _auth_service
