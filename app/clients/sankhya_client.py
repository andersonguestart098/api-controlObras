import asyncio
import logging
from typing import Any

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import SankhyaRequestError
from app.services.sankhya_auth import (
    SankhyaAuthService,
    get_sankhya_auth_service,
)


logger = logging.getLogger(__name__)


class SankhyaClient:
    """
    Cliente HTTP reutilizável para comunicação com o Sankhya.

    Consultas de leitura podem ser repetidas automaticamente
    quando houver uma falha transitória de conexão.
    """

    MAX_TENTATIVAS = 3
    TEMPO_BASE_RETRY_SEGUNDOS = 0.8

    # Somente serviços seguros para repetição automática.
    SERVICOS_COM_RETRY = frozenset(
        {
            "DbExplorerSP.executeQuery",
        }
    )

    STATUS_HTTP_TRANSITORIOS = frozenset(
        {
            429,
            502,
            503,
            504,
        }
    )

    ERROS_TRANSITORIOS = (
        httpx.ReadError,
        httpx.ConnectError,
        httpx.WriteError,
        httpx.RemoteProtocolError,
    )

    def __init__(
        self,
        settings: Settings,
        auth_service: SankhyaAuthService,
    ) -> None:
        self._settings = settings
        self._auth_service = auth_service

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=15.0,
                read=settings.sankhya_timeout_seconds,
                write=30.0,
                pool=15.0,
            ),
            limits=httpx.Limits(
                max_connections=(
                    settings.sankhya_max_connections
                ),
                max_keepalive_connections=(
                    settings
                    .sankhya_max_keepalive_connections
                ),
                # Evita manter conexões antigas por muito tempo.
                keepalive_expiry=30.0,
            ),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def execute_service(
        self,
        service_name: str,
        request_body: dict[str, Any],
        *,
        retry_on_unauthorized: bool = True,
        retry_on_transient_error: bool | None = None,
    ) -> dict[str, Any]:
        """
        Executa um serviço Sankhya.

        O retry de conexão é habilitado automaticamente
        somente para serviços considerados seguros.

        Para outros serviços, ele pode ser habilitado
        explicitamente com retry_on_transient_error=True.
        """

        permitir_retry = (
            service_name in self.SERVICOS_COM_RETRY
            if retry_on_transient_error is None
            else retry_on_transient_error
        )

        quantidade_tentativas = (
            self.MAX_TENTATIVAS
            if permitir_retry
            else 1
        )

        payload = {
            "serviceName": service_name,
            "requestBody": request_body,
        }

        params = {
            "serviceName": service_name,
            "outputType": "json",
        }

        ultimo_erro: Exception | None = None

        for tentativa in range(
            1,
            quantidade_tentativas + 1,
        ):
            token = await self._auth_service.get_token()

            try:
                response = await self._client.post(
                    self._settings.sankhya_base_url,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    json=payload,
                )

            except httpx.TimeoutException as exc:
                ultimo_erro = exc

                if self._pode_tentar_novamente(
                    permitir_retry=permitir_retry,
                    tentativa=tentativa,
                    quantidade_tentativas=(
                        quantidade_tentativas
                    ),
                ):
                    await self._aguardar_nova_tentativa(
                        service_name=service_name,
                        tentativa=tentativa,
                        motivo=type(exc).__name__,
                    )
                    continue

                raise SankhyaRequestError(
                    f"Timeout ao executar {service_name} "
                    f"após {tentativa} tentativa(s)."
                ) from exc

            except self.ERROS_TRANSITORIOS as exc:
                ultimo_erro = exc

                if self._pode_tentar_novamente(
                    permitir_retry=permitir_retry,
                    tentativa=tentativa,
                    quantidade_tentativas=(
                        quantidade_tentativas
                    ),
                ):
                    await self._aguardar_nova_tentativa(
                        service_name=service_name,
                        tentativa=tentativa,
                        motivo=type(exc).__name__,
                    )
                    continue

                raise SankhyaRequestError(
                    f"Erro de conexão ao executar "
                    f"{service_name} após "
                    f"{tentativa} tentativa(s)."
                ) from exc

            except httpx.RequestError as exc:
                # Demais erros HTTP não são considerados
                # necessariamente transitórios.
                raise SankhyaRequestError(
                    f"Erro de conexão ao executar "
                    f"{service_name}."
                ) from exc

            if (
                response.status_code == 401
                and retry_on_unauthorized
            ):
                logger.warning(
                    "Token Sankhya rejeitado ao executar %s. "
                    "Renovando token e tentando novamente.",
                    service_name,
                )

                await self._auth_service.refresh_token()

                return await self.execute_service(
                    service_name,
                    request_body,
                    retry_on_unauthorized=False,
                    retry_on_transient_error=(
                        permitir_retry
                    ),
                )

            if (
                response.status_code
                in self.STATUS_HTTP_TRANSITORIOS
                and self._pode_tentar_novamente(
                    permitir_retry=permitir_retry,
                    tentativa=tentativa,
                    quantidade_tentativas=(
                        quantidade_tentativas
                    ),
                )
            ):
                await self._aguardar_nova_tentativa(
                    service_name=service_name,
                    tentativa=tentativa,
                    motivo=(
                        f"HTTP {response.status_code}"
                    ),
                )
                continue

            data = self._parse_response_json(
                response=response,
                service_name=service_name,
            )

            if response.is_error:
                raise SankhyaRequestError(
                    f"Erro HTTP ao executar "
                    f"{service_name}.",
                    status_code=response.status_code,
                    response_data=data,
                )

            if str(data.get("status")) == "0":
                raise SankhyaRequestError(
                    data.get(
                        "statusMessage",
                        f"Erro no serviço {service_name}.",
                    ),
                    response_data=data,
                )

            return data

        raise SankhyaRequestError(
            f"Erro de conexão ao executar {service_name} "
            f"após {quantidade_tentativas} tentativas."
        ) from ultimo_erro

    @staticmethod
    def _pode_tentar_novamente(
        *,
        permitir_retry: bool,
        tentativa: int,
        quantidade_tentativas: int,
    ) -> bool:
        return (
            permitir_retry
            and tentativa < quantidade_tentativas
        )

    async def _aguardar_nova_tentativa(
        self,
        *,
        service_name: str,
        tentativa: int,
        motivo: str,
    ) -> None:
        """
        Aplica espera progressiva:

        tentativa 1 -> 0,8 segundo
        tentativa 2 -> 1,6 segundo
        """

        tempo_espera = (
            self.TEMPO_BASE_RETRY_SEGUNDOS
            * tentativa
        )

        logger.warning(
            "Falha transitória no Sankhya. "
            "Serviço=%s, tentativa=%s/%s, motivo=%s. "
            "Nova tentativa em %.1f segundo(s).",
            service_name,
            tentativa,
            self.MAX_TENTATIVAS,
            motivo,
            tempo_espera,
        )

        await asyncio.sleep(tempo_espera)

    @staticmethod
    def _parse_response_json(
        *,
        response: httpx.Response,
        service_name: str,
    ) -> dict[str, Any]:
        try:
            data = response.json()

        except ValueError as exc:
            corpo_resposta = response.text.strip()

            if len(corpo_resposta) > 1000:
                corpo_resposta = (
                    corpo_resposta[:1000] + "..."
                )

            raise SankhyaRequestError(
                "O Sankhya retornou uma resposta não JSON.",
                status_code=response.status_code,
                response_data={
                    "service_name": service_name,
                    "response_body": corpo_resposta,
                },
            ) from exc

        if not isinstance(data, dict):
            raise SankhyaRequestError(
                "O Sankhya retornou uma estrutura JSON "
                "inesperada.",
                status_code=response.status_code,
                response_data=data,
            )

        return data


_client: SankhyaClient | None = None


def get_sankhya_client(
    settings: Settings = Depends(get_settings),
    auth_service: SankhyaAuthService = Depends(
        get_sankhya_auth_service
    ),
) -> SankhyaClient:
    global _client

    if _client is None:
        _client = SankhyaClient(
            settings,
            auth_service,
        )

    return _client