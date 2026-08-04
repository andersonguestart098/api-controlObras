import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import SankhyaAuthenticationError


logger = logging.getLogger(__name__)


class SankhyaAuthService:
    """
    Mantém um único token Sankhya em memória por processo.

    Fluxo:
    1. A primeira chamada autentica.
    2. Todas as rotas reutilizam o mesmo token.
    3. Uma nova autenticação só acontece quando o token expira
       ou quando o Sankhya devolve HTTP 401.
    4. O lock impede duas renovações simultâneas.
    """

    MAX_TENTATIVAS = 3
    MARGEM_EXPIRACAO_SEGUNDOS = 10

    STATUS_HTTP_TRANSITORIOS = frozenset(
        {
            429,
            502,
            503,
            504,
        }
    )

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._settings = settings

        self._access_token: str | None = None
        self._token_expiration: datetime | None = None

        self._refresh_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=15.0,
                read=settings.sankhya_timeout_seconds,
                write=30.0,
                pool=15.0,
            ),
            limits=httpx.Limits(
                max_connections=5,
                max_keepalive_connections=2,
                keepalive_expiry=30.0,
            ),
            headers={
                "Accept": "application/json",
            },
        )

    @property
    def token_expiration(
        self,
    ) -> datetime | None:
        return self._token_expiration

    def token_is_valid(self) -> bool:
        """
        Apenas verifica o token em memória.
        Não realiza nenhuma chamada HTTP.
        """

        if (
            not self._access_token
            or not self._token_expiration
        ):
            return False

        margem = timedelta(
            seconds=self.MARGEM_EXPIRACAO_SEGUNDOS
        )

        return (
            datetime.now(timezone.utc)
            < self._token_expiration - margem
        )

    async def get_token(self) -> str:
        """
        Chamado pelas rotas/clients.

        Enquanto o token estiver válido, apenas devolve a string
        já armazenada em memória. Não autentica novamente.
        """

        if (
            self._access_token
            and self.token_is_valid()
        ):
            return self._access_token

        return await self.refresh_token()

    async def refresh_token(
        self,
        *,
        force: bool = False,
        rejected_token: str | None = None,
    ) -> str:
        """
        Renova o token quando necessário.

        force=False:
            autentica apenas se não existir token válido.

        force=True:
            usado depois de HTTP 401 ou por renovação manual.

        rejected_token:
            token que recebeu 401. Se outra chamada já tiver
            trocado esse token enquanto aguardávamos o lock,
            reutiliza o token novo e não autentica novamente.
        """

        async with self._refresh_lock:
            if not force:
                if (
                    self._access_token
                    and self.token_is_valid()
                ):
                    return self._access_token

            if (
                force
                and rejected_token
                and self._access_token
                and self._access_token != rejected_token
                and self.token_is_valid()
            ):
                return self._access_token

            response = await self._authenticate_with_retry()
            payload = self._parse_response_json(response)

            access_token = payload.get("access_token")

            if not access_token:
                raise SankhyaAuthenticationError(
                    "O Sankhya não retornou access_token."
                )

            try:
                expires_in = int(
                    payload.get(
                        "expires_in",
                        300,
                    )
                )
            except (TypeError, ValueError):
                expires_in = 300

            # Não aumenta artificialmente a validade retornada
            # pelo Sankhya.
            expires_in = max(expires_in, 1)

            self._access_token = str(access_token)
            self._token_expiration = (
                datetime.now(timezone.utc)
                + timedelta(seconds=expires_in)
            )

            logger.info(
                "Novo token Sankhya obtido. "
                "Validade informada: %s segundo(s). "
                "Expira em: %s.",
                expires_in,
                self._token_expiration.isoformat(),
            )

            return self._access_token

    async def _authenticate_with_retry(
        self,
    ) -> httpx.Response:
        headers = {
            "X-Token": self._settings.sankhya_x_token,
            "Content-Type": (
                "application/x-www-form-urlencoded"
            ),
            "Accept": "application/json",
        }

        data = {
            "grant_type": "client_credentials",
            "client_id": (
                self._settings.sankhya_client_id
            ),
            "client_secret": (
                self._settings.sankhya_client_secret
            ),
        }

        ultimo_erro: Exception | None = None

        for tentativa in range(
            1,
            self.MAX_TENTATIVAS + 1,
        ):
            try:
                response = await self._client.post(
                    self._settings.sankhya_auth_url,
                    headers=headers,
                    data=data,
                )

            except httpx.TimeoutException as exc:
                ultimo_erro = exc

                if tentativa >= self.MAX_TENTATIVAS:
                    raise SankhyaAuthenticationError(
                        "Timeout ao autenticar no Sankhya "
                        f"após {tentativa} tentativa(s)."
                    ) from exc

                await self._aguardar_retry(
                    tentativa=tentativa,
                    motivo=type(exc).__name__,
                )
                continue

            except httpx.RequestError as exc:
                ultimo_erro = exc

                if tentativa >= self.MAX_TENTATIVAS:
                    raise SankhyaAuthenticationError(
                        "Não foi possível conectar ao serviço "
                        "de autenticação do Sankhya após "
                        f"{tentativa} tentativa(s)."
                    ) from exc

                await self._aguardar_retry(
                    tentativa=tentativa,
                    motivo=type(exc).__name__,
                )
                continue

            if (
                response.status_code
                in self.STATUS_HTTP_TRANSITORIOS
            ):
                if tentativa >= self.MAX_TENTATIVAS:
                    raise SankhyaAuthenticationError(
                        "Falha ao autenticar no Sankhya. "
                        f"HTTP {response.status_code}. "
                        "Limite de tentativas atingido. "
                        f"Resposta: "
                        f"{self._safe_parse_response(response)}"
                    )

                tempo_espera = self._get_retry_delay(
                    response=response,
                    tentativa=tentativa,
                )

                logger.warning(
                    "Autenticação Sankhya recebeu HTTP %s. "
                    "Tentativa %s/%s. "
                    "Nova tentativa em %.1f segundo(s).",
                    response.status_code,
                    tentativa,
                    self.MAX_TENTATIVAS,
                    tempo_espera,
                )

                await asyncio.sleep(tempo_espera)
                continue

            try:
                response.raise_for_status()

            except httpx.HTTPStatusError as exc:
                raise SankhyaAuthenticationError(
                    "Falha ao autenticar no Sankhya. "
                    f"HTTP {response.status_code}. "
                    f"Resposta: "
                    f"{self._safe_parse_response(response)}"
                ) from exc

            return response

        raise SankhyaAuthenticationError(
            "Não foi possível autenticar no Sankhya."
        ) from ultimo_erro

    async def _aguardar_retry(
        self,
        *,
        tentativa: int,
        motivo: str,
    ) -> None:
        tempo_espera = min(
            float(2 ** (tentativa - 1)),
            10.0,
        )

        logger.warning(
            "Falha transitória na autenticação Sankhya. "
            "Tentativa %s/%s, motivo=%s. "
            "Nova tentativa em %.1f segundo(s).",
            tentativa,
            self.MAX_TENTATIVAS,
            motivo,
            tempo_espera,
        )

        await asyncio.sleep(tempo_espera)

    @staticmethod
    def _get_retry_delay(
        *,
        response: httpx.Response,
        tentativa: int,
    ) -> float:
        retry_after = response.headers.get(
            "Retry-After"
        )

        if retry_after:
            try:
                return min(
                    max(float(retry_after), 1.0),
                    30.0,
                )
            except ValueError:
                pass

        return min(
            float(2 ** (tentativa - 1)),
            10.0,
        )

    @staticmethod
    def _parse_response_json(
        response: httpx.Response,
    ) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise SankhyaAuthenticationError(
                "O Sankhya retornou uma resposta não JSON "
                "durante a autenticação."
            ) from exc

        if not isinstance(payload, dict):
            raise SankhyaAuthenticationError(
                "O Sankhya retornou uma estrutura inesperada "
                "durante a autenticação."
            )

        return payload

    @staticmethod
    def _safe_parse_response(
        response: httpx.Response,
    ) -> Any:
        if not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            texto = response.text.strip()

            if len(texto) > 500:
                texto = texto[:500] + "..."

            return texto

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()


_auth_service: SankhyaAuthService | None = None


def get_sankhya_auth_service(
    settings: Settings = Depends(get_settings),
) -> SankhyaAuthService:
    """
    Retorna a mesma instância durante toda a vida do processo.
    Portanto, todas as rotas compartilham o mesmo token.
    """

    global _auth_service

    if _auth_service is None:
        _auth_service = SankhyaAuthService(
            settings
        )

    return _auth_service


async def close_sankhya_auth_service() -> None:
    global _auth_service

    if _auth_service is not None:
        await _auth_service.close()

    _auth_service = None