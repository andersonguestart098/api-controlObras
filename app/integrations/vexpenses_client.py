import asyncio
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class VExpensesAPIError(RuntimeError):
    """
    Erro ocorrido durante uma chamada à API VExpenses.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_data: Any | None = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.response_data = response_data


class VExpensesClient:
    """
    Client HTTP responsável pela comunicação com a API VExpenses.

    Não contém regras de negócio. Apenas:
    - autenticação;
    - chamadas HTTP;
    - timeout;
    - retry para rate limit;
    - tratamento de erros.
    """

    def __init__(
        self,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()

        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            method="GET",
            endpoint=endpoint,
            params=params,
        )

    async def post(
        self,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            method="POST",
            endpoint=endpoint,
            params=params,
            json=json,
        )

    async def put(
        self,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            method="PUT",
            endpoint=endpoint,
            params=params,
            json=json,
        )

    async def delete(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            method="DELETE",
            endpoint=endpoint,
            params=params,
        )

    async def _request(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        client = await self._get_client()

        endpoint_normalizado = endpoint.lstrip("/")

        max_tentativas = 4

        for tentativa in range(max_tentativas):
            try:
                response = await client.request(
                    method=method,
                    url=endpoint_normalizado,
                    params=params,
                    json=json,
                )

            except httpx.TimeoutException as exc:
                raise VExpensesAPIError(
                    "Tempo limite excedido ao consultar a VExpenses."
                ) from exc

            except httpx.RequestError as exc:
                raise VExpensesAPIError(
                    "Não foi possível conectar à API VExpenses."
                ) from exc

            if response.status_code == 429:
                ultima_tentativa = tentativa == max_tentativas - 1

                if ultima_tentativa:
                    raise VExpensesAPIError(
                        "Limite de requisições da VExpenses atingido.",
                        status_code=response.status_code,
                        response_data=self._parse_response(response),
                    )

                tempo_espera = self._get_retry_delay(
                    response=response,
                    tentativa=tentativa,
                )

                await asyncio.sleep(tempo_espera)
                continue

            if response.is_error:
                raise VExpensesAPIError(
                    self._build_error_message(response),
                    status_code=response.status_code,
                    response_data=self._parse_response(response),
                )

            return self._parse_response(response)

        raise VExpensesAPIError(
            "Não foi possível concluir a chamada à VExpenses."
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Cria o AsyncClient somente na primeira utilização
        e reaproveita o pool de conexões nas chamadas seguintes.
        """

        if self._client is not None and not self._client.is_closed:
            return self._client

        async with self._client_lock:
            if self._client is not None and not self._client.is_closed:
                return self._client

            limits = httpx.Limits(
                max_connections=(
                    self._settings.vexpenses_max_connections
                ),
                max_keepalive_connections=(
                    self._settings
                    .vexpenses_max_keepalive_connections
                ),
            )

            timeout = httpx.Timeout(
                self._settings.vexpenses_timeout_seconds
            )

            self._client = httpx.AsyncClient(
                base_url=(
                    self._settings
                    .vexpenses_base_url
                    .rstrip("/")
                    + "/"
                ),
                headers={
                    "Authorization": (
                        self._settings
                        .vexpenses_token
                        .get_secret_value()
                    ),
                    "Accept": "application/json",
                },
                timeout=timeout,
                limits=limits,
            )

            return self._client

    async def aclose(self) -> None:
        """
        Fecha o pool de conexões HTTP no encerramento da aplicação.
        """

        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

        self._client = None

    @staticmethod
    def _parse_response(
        response: httpx.Response,
    ) -> Any:
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            return {
                "raw_response": response.text,
            }

    @staticmethod
    def _get_retry_delay(
        *,
        response: httpx.Response,
        tentativa: int,
    ) -> float:
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass

        # 1, 2, 4 segundos
        return float(2**tentativa)

    @staticmethod
    def _build_error_message(
        response: httpx.Response,
    ) -> str:
        messages = {
            400: "Requisição inválida enviada à VExpenses.",
            401: "Token da VExpenses inválido ou não autorizado.",
            403: "Acesso negado pela API VExpenses.",
            404: "Recurso não encontrado na VExpenses.",
            422: "Dados rejeitados pela API VExpenses.",
            500: "Erro interno retornado pela VExpenses.",
            502: "A VExpenses está temporariamente indisponível.",
            503: "O serviço da VExpenses está indisponível.",
            504: "A VExpenses demorou demais para responder.",
        }

        return messages.get(
            response.status_code,
            (
                "Erro ao consultar a API VExpenses. "
                f"Status HTTP: {response.status_code}."
            ),
        )


_vexpenses_client: VExpensesClient | None = None


def get_vexpenses_client() -> VExpensesClient:
    """
    Retorna uma única instância do client por processo da aplicação.
    """

    global _vexpenses_client

    if _vexpenses_client is None:
        _vexpenses_client = VExpensesClient()

    return _vexpenses_client


async def close_vexpenses_client() -> None:
    """
    Função utilizada no shutdown/lifespan do FastAPI.
    """

    global _vexpenses_client

    if _vexpenses_client is not None:
        await _vexpenses_client.aclose()

    _vexpenses_client = None