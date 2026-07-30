import asyncio
import logging
from typing import Any

from fastapi import Depends

from app.analytics.normalizers import (
    frame_to_json_records,
    normalize_rows,
)
from app.clients.sankhya_client import (
    SankhyaClient,
    get_sankhya_client,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import SankhyaQueryResponseError
from app.queries.registry import load_sql
from app.schemas.filters import DashboardFilters
from app.schemas.query import SankhyaQueryDefinition


logger = logging.getLogger(__name__)


class SankhyaQueryService:
    def __init__(
        self,
        client: SankhyaClient,
        settings: Settings,
    ) -> None:
        self._client = client

        self._semaphore = asyncio.Semaphore(
            settings.sankhya_max_concurrent_queries
        )

    async def execute_query(
        self,
        definition: SankhyaQueryDefinition,
        filters: DashboardFilters,
    ) -> list[dict[str, Any]]:
        sql = load_sql(definition)

        sql = self._apply_filters(
            sql=sql,
            definition=definition,
            filters=filters,
        )

        request_body = {
            "sql": sql,
        }

        async with self._semaphore:
            response = await self._client.execute_service(
                "DbExplorerSP.executeQuery",
                request_body,
            )

        try:
            raw_rows, _ = self._extract_rows(
                response=response,
            )
        except SankhyaQueryResponseError:
            logger.exception(
                "Falha ao interpretar resposta do DbExplorer. "
                "Consulta: %s | Arquivo: %s | CODPROJ: %s | "
                "Data inicial: %s | Data final: %s",
                definition.code,
                definition.filename,
                filters.codproj,
                filters.dtneg_inicial,
                filters.dtneg_final,
            )
            raise

        frame = normalize_rows(
            rows=raw_rows,
        )

        normalized_rows = frame_to_json_records(frame)

        self._validate_columns(
            definition=definition,
            rows=normalized_rows,
        )

        return normalized_rows

    @staticmethod
    def _apply_filters(
        sql: str,
        definition: SankhyaQueryDefinition,
        filters: DashboardFilters,
    ) -> str:
        """
        Aplica os filtros globais do dashboard.

        CODPROJ é obrigatório.
        O período é opcional.
        """

        # CODPROJ é obrigatório e validado
        # como inteiro pelo Pydantic.
        sql = sql.replace(
            "{{CODPROJ}}",
            str(filters.codproj),
        )

        if (
            definition.supports_period
            and filters.dtneg_inicial is not None
        ):
            dtneg_inicial = (
                filters.dtneg_inicial.strftime(
                    "%Y-%m-%d"
                )
            )

            sql = sql.replace(
                "/*FILTRO_DTNEG_INICIAL*/",
                (
                    "AND CAB.DTNEG >= "
                    f"TO_DATE("
                    f"'{dtneg_inicial}', "
                    f"'YYYY-MM-DD'"
                    f")"
                ),
            )
        else:
            sql = sql.replace(
                "/*FILTRO_DTNEG_INICIAL*/",
                "",
            )

        if (
            definition.supports_period
            and filters.dtneg_final is not None
        ):
            dtneg_final = (
                filters.dtneg_final.strftime(
                    "%Y-%m-%d"
                )
            )

            sql = sql.replace(
                "/*FILTRO_DTNEG_FINAL*/",
                (
                    "AND CAB.DTNEG < "
                    f"TO_DATE("
                    f"'{dtneg_final}', "
                    f"'YYYY-MM-DD'"
                    f") + 1"
                ),
            )
        else:
            sql = sql.replace(
                "/*FILTRO_DTNEG_FINAL*/",
                "",
            )

        SankhyaQueryService._validate_processed_sql(
            sql
        )

        return sql

    @staticmethod
    def _validate_processed_sql(sql: str) -> None:
        """
        Garante que nenhum marcador dinâmico ficou sem substituição.
        """

        if "{{" in sql or "}}" in sql:
            raise SankhyaQueryResponseError(
                "A consulta contém marcadores obrigatórios "
                "que não foram substituídos."
            )

        if "/*FILTRO_" in sql:
            raise SankhyaQueryResponseError(
                "A consulta contém filtros dinâmicos "
                "que não foram processados."
            )

    @staticmethod
    def _extract_rows(
        response: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Extrai as linhas retornadas pelo DbExplorer.

        Algumas versões do Sankhya retornam responseBody vazio quando
        a consulta não encontra registros. Esse cenário é válido e deve
        ser convertido para uma lista vazia, sem derrubar o dashboard.
        """

        if not isinstance(response, dict):
            raise SankhyaQueryResponseError(
                "O DbExplorer retornou uma resposta em formato "
                f"inválido: {type(response).__name__}."
            )

        service_response = response.get("serviceResponse")

        if isinstance(service_response, dict):
            response_data = service_response
        else:
            response_data = response

        status = response_data.get("status")
        status_message = (
            response_data.get("statusMessage")
            or response_data.get("statusMessageError")
            or response_data.get("message")
            or ""
        )

        if SankhyaQueryService._is_error_status(status):
            raise SankhyaQueryResponseError(
                "Erro retornado pelo DbExplorerSP.executeQuery: "
                f"{status_message or 'sem mensagem de erro'}."
            )

        has_response_body = "responseBody" in response_data
        body = response_data.get("responseBody")

        # O Sankhya pode devolver responseBody vazio quando a consulta
        # é válida, mas não encontrou nenhum registro.
        if has_response_body and body in (None, {}, []):
            return [], []

        # Compatibilidade com respostas em que rows/result aparecem
        # diretamente no objeto principal, sem responseBody.
        if not has_response_body:
            direct_body_keys = {
                "rows",
                "fieldsMetadata",
                "fields",
                "result",
                "resultSet",
                "response",
            }

            if direct_body_keys.intersection(response_data.keys()):
                body = response_data
            else:
                raise SankhyaQueryResponseError(
                    "A resposta do DbExplorerSP.executeQuery não contém "
                    "responseBody nem uma estrutura de resultado conhecida. "
                    f"Chaves encontradas: {list(response_data.keys())}. "
                    "Mensagem do Sankhya: "
                    f"{status_message or 'não informada'}."
                )

        if not isinstance(body, dict):
            raise SankhyaQueryResponseError(
                "Formato de responseBody não reconhecido. "
                f"Tipo recebido: {type(body).__name__}. "
                "Mensagem do Sankhya: "
                f"{status_message or 'não informada'}."
            )

        direct_rows = body.get("rows")

        direct_fields = (
            body.get("fieldsMetadata")
            or body.get("fields")
            or []
        )

        if isinstance(direct_rows, list):
            metadata = SankhyaQueryService._ensure_metadata_list(
                direct_fields
            )

            if not direct_rows:
                return [], metadata

            # Algumas versões podem retornar cada linha
            # diretamente como objeto.
            if isinstance(direct_rows[0], dict):
                return direct_rows, metadata

            # Formato padrão do DbExplorer:
            #
            # fieldsMetadata:
            #   [{"name": "NUNOTA"}, {"name": "VLRNOTA"}]
            #
            # rows:
            #   [[102540, 3897]]
            if isinstance(direct_fields, list):
                column_names = (
                    SankhyaQueryService._extract_column_names(
                        direct_fields
                    )
                )

                mapped_rows = (
                    SankhyaQueryService._map_rows_to_dicts(
                        column_names=column_names,
                        rows=direct_rows,
                    )
                )

                return mapped_rows, metadata

        # Compatibilidade com versões que colocam o resultado
        # dentro de responseBody.result ou resultSet.
        result = (
            body.get("result")
            or body.get("resultSet")
            or {}
        )

        if isinstance(result, dict):
            result_rows = result.get("rows")

            result_fields = (
                result.get("fieldsMetadata")
                or result.get("fields")
                or []
            )

            if isinstance(result_rows, list):
                metadata = (
                    SankhyaQueryService._ensure_metadata_list(
                        result_fields
                    )
                )

                if not result_rows:
                    return [], metadata

                if isinstance(result_rows[0], dict):
                    return result_rows, metadata

                if isinstance(result_fields, list):
                    column_names = (
                        SankhyaQueryService._extract_column_names(
                            result_fields
                        )
                    )

                    mapped_rows = (
                        SankhyaQueryService._map_rows_to_dicts(
                            column_names=column_names,
                            rows=result_rows,
                        )
                    )

                    return mapped_rows, metadata

        response_rows = body.get("response")

        if isinstance(response_rows, list):
            if not response_rows:
                return [], []

            if isinstance(response_rows[0], dict):
                return response_rows, []

        body_keys = list(body.keys())

        raise SankhyaQueryResponseError(
            "Formato da resposta do "
            "DbExplorerSP.executeQuery não reconhecido. "
            f"Tipo de responseBody: {type(body).__name__}. "
            f"Chaves encontradas em responseBody: {body_keys}. "
            "Mensagem do Sankhya: "
            f"{status_message or 'não informada'}."
        )

    @staticmethod
    def _is_error_status(status: Any) -> bool:
        """
        Identifica os valores de status usados pelo Sankhya para erro.
        """

        if status is None:
            return False

        if status is False:
            return True

        if isinstance(status, (int, float)):
            return status == 0

        normalized_status = str(status).strip().lower()

        return normalized_status in {
            "0",
            "false",
            "error",
            "erro",
            "failed",
            "failure",
        }

    @staticmethod
    def _ensure_metadata_list(
        fields: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(fields, list):
            return []

        return [
            field
            for field in fields
            if isinstance(field, dict)
        ]

    @staticmethod
    def _extract_column_names(
        fields: list[Any],
    ) -> list[str]:
        column_names: list[str] = []

        for field in fields:
            if isinstance(field, dict):
                column_name = (
                    field.get("name")
                    or field.get("fieldName")
                    or field.get("columnName")
                )
            else:
                column_name = str(field)

            if not column_name:
                raise SankhyaQueryResponseError(
                    "O DbExplorer retornou uma coluna "
                    "sem nome em fieldsMetadata."
                )

            column_names.append(
                str(column_name)
            )

        return column_names

    @staticmethod
    def _map_rows_to_dicts(
        column_names: list[str],
        rows: list[Any],
    ) -> list[dict[str, Any]]:
        mapped_rows: list[dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, (list, tuple)):
                raise SankhyaQueryResponseError(
                    "O DbExplorer retornou uma linha "
                    "em formato inesperado."
                )

            if len(row) != len(column_names):
                raise SankhyaQueryResponseError(
                    "A quantidade de valores da linha retornada "
                    "pelo DbExplorer não corresponde à quantidade "
                    "de colunas do fieldsMetadata."
                )

            mapped_rows.append(
                dict(
                    zip(
                        column_names,
                        row,
                        strict=True,
                    )
                )
            )

        return mapped_rows

    @staticmethod
    def _validate_columns(
        definition: SankhyaQueryDefinition,
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return

        returned = {
            str(column).upper()
            for column in rows[0]
        }

        expected = {
            str(column).upper()
            for column in definition.expected_columns
        }

        missing = expected - returned

        if missing:
            raise SankhyaQueryResponseError(
                f"Consulta '{definition.code}' não retornou "
                f"as colunas esperadas: {sorted(missing)}. "
                f"Colunas efetivamente retornadas: {sorted(returned)}"
            )


_query_service: SankhyaQueryService | None = None


def get_sankhya_query_service(
    client: SankhyaClient = Depends(get_sankhya_client),
    settings: Settings = Depends(get_settings),
) -> SankhyaQueryService:
    global _query_service

    if _query_service is None:
        _query_service = SankhyaQueryService(
            client=client,
            settings=settings,
        )

    return _query_service