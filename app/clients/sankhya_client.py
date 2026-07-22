from typing import Any

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import SankhyaRequestError
from app.services.sankhya_auth import SankhyaAuthService, get_sankhya_auth_service


class SankhyaClient:
    def __init__(self, settings: Settings, auth_service: SankhyaAuthService) -> None:
        self._settings = settings
        self._auth_service = auth_service
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.sankhya_timeout_seconds, connect=15.0),
            limits=httpx.Limits(
                max_connections=settings.sankhya_max_connections,
                max_keepalive_connections=settings.sankhya_max_keepalive_connections,
            ),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def execute_service(
        self,
        service_name: str,
        request_body: dict[str, Any],
        *,
        retry_on_unauthorized: bool = True,
    ) -> dict[str, Any]:
        token = await self._auth_service.get_token()
        payload = {"serviceName": service_name, "requestBody": request_body}
        params = {"serviceName": service_name, "outputType": "json"}

        try:
            response = await self._client.post(
                self._settings.sankhya_base_url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise SankhyaRequestError(f"Timeout ao executar {service_name}.") from exc
        except httpx.RequestError as exc:
            raise SankhyaRequestError(f"Erro de conexão ao executar {service_name}.") from exc

        if response.status_code == 401 and retry_on_unauthorized:
            await self._auth_service.refresh_token()
            return await self.execute_service(
                service_name,
                request_body,
                retry_on_unauthorized=False,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SankhyaRequestError(
                "O Sankhya retornou uma resposta não JSON.",
                status_code=response.status_code,
            ) from exc

        if response.is_error:
            raise SankhyaRequestError(
                f"Erro HTTP ao executar {service_name}.",
                status_code=response.status_code,
                response_data=data,
            )

        if str(data.get("status")) == "0":
            raise SankhyaRequestError(
                data.get("statusMessage", f"Erro no serviço {service_name}."),
                response_data=data,
            )

        return data


_client: SankhyaClient | None = None


def get_sankhya_client(
    settings: Settings = Depends(get_settings),
    auth_service: SankhyaAuthService = Depends(get_sankhya_auth_service),
) -> SankhyaClient:
    global _client
    if _client is None:
        _client = SankhyaClient(settings, auth_service)
    return _client
