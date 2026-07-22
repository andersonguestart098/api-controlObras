import asyncio
from typing import Any

from fastapi import Depends

from app.analytics.dashboard_analytics import (
    DashboardAnalytics,
)
from app.queries.registry import QUERY_REGISTRY
from app.schemas.filters import DashboardFilters
from app.schemas.query import (
    SankhyaQueryDefinition,
)
from app.services.sankhya_query_service import (
    SankhyaQueryService,
    get_sankhya_query_service,
)


class DashboardService:
    def __init__(
        self,
        query_service: SankhyaQueryService,
    ) -> None:
        self._query_service = query_service

    async def get_kpis(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        projeto_definition = self._get_definition(
            "projeto"
        )

        notas_definition = self._get_definition(
            "notas"
        )

        itens_notas_definition = self._get_definition(
            "itens_notas"
        )

        interno_obras_definition = (
            self._get_definition(
                "pagamento_interno_obras"
            )
        )

        remessas_definition = self._get_definition(
            "remessas"
        )

        itens_remessas_definition = (
            self._get_definition(
                "itens_remessas"
            )
        )

        notas_impostos_definition = (
            self._get_definition(
                "notas_impostos"
            )
        )

        (
            projeto_rows,
            notas_rows,
            itens_notas_rows,
            interno_obras_rows,
            remessas_rows,
            itens_remessas_rows,
            notas_impostos_rows,
        ) = await asyncio.gather(
            self._query_service.execute_query(
                projeto_definition,
                filters,
            ),
            self._query_service.execute_query(
                notas_definition,
                filters,
            ),
            self._query_service.execute_query(
                itens_notas_definition,
                filters,
            ),
            self._query_service.execute_query(
                interno_obras_definition,
                filters,
            ),
            self._query_service.execute_query(
                remessas_definition,
                filters,
            ),
            self._query_service.execute_query(
                itens_remessas_definition,
                filters,
            ),
            self._query_service.execute_query(
                notas_impostos_definition,
                filters,
            ),
        )

        projeto = self._build_projeto(
            projeto_rows=projeto_rows,
            filters=filters,
        )

        kpis = DashboardAnalytics.build_kpis(
            notas=notas_rows,
            itens_notas=itens_notas_rows,
            interno_obras=interno_obras_rows,
            remessas=remessas_rows,
            itens_remessas=itens_remessas_rows,
            notas_impostos=notas_impostos_rows,
        )

        return {
            "filters": filters.model_dump(
                mode="json"
            ),
            "projeto": projeto,
            "kpis": kpis,
        }

    async def load_all_raw(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        definitions = list(
            QUERY_REGISTRY.values()
        )

        results = await asyncio.gather(
            *(
                self._query_service.execute_query(
                    definition,
                    filters,
                )
                for definition in definitions
            )
        )

        queries: dict[str, Any] = {}

        for definition, rows in zip(
            definitions,
            results,
            strict=True,
        ):
            queries[definition.code] = {
                "name": definition.name,
                "granularity": (
                    definition.granularity
                ),
                "count": len(rows),
                "data": rows,
            }

        return {
            "filters": filters.model_dump(
                mode="json"
            ),
            "queries": queries,
        }

    async def get_remessas_control(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        remessas_definition = self._get_definition(
            "remessas"
        )

        itens_remessas_definition = (
            self._get_definition(
                "itens_remessas"
            )
        )

        (
            remessas_rows,
            itens_remessas_rows,
        ) = await asyncio.gather(
            self._query_service.execute_query(
                remessas_definition,
                filters,
            ),
            self._query_service.execute_query(
                itens_remessas_definition,
                filters,
            ),
        )

        total_row = next(
            (
                row
                for row in itens_remessas_rows
                if str(
                    row.get(
                        "status_item",
                        "",
                    )
                ).upper()
                == "TOTAL"
            ),
            None,
        )

        itens = [
            row
            for row in itens_remessas_rows
            if str(
                row.get(
                    "status_item",
                    "",
                )
            ).upper()
            != "TOTAL"
        ]

        resumo = {
            "qtd_total": (
                total_row.get(
                    "qtd_total",
                    0,
                )
                if total_row
                else 0
            ),
            "qtd_entregue": (
                total_row.get(
                    "qtd_entregue",
                    0,
                )
                if total_row
                else 0
            ),
            "qtd_pendente": (
                total_row.get(
                    "qtd_pendente",
                    0,
                )
                if total_row
                else 0
            ),
            "vlr_total_item": (
                total_row.get(
                    "vlr_total_item",
                    0,
                )
                if total_row
                else 0
            ),
            "vlr_entregue_item": (
                total_row.get(
                    "vlr_entregue_item",
                    0,
                )
                if total_row
                else 0
            ),
            "vlr_saldo_item": (
                total_row.get(
                    "vlr_saldo_item",
                    0,
                )
                if total_row
                else 0
            ),
            "custo_total": (
                total_row.get(
                    "custo_total",
                    0,
                )
                if total_row
                else 0
            ),
            "custo_entregue": (
                total_row.get(
                    "custo_entregue",
                    0,
                )
                if total_row
                else 0
            ),
            "custo_pendente": (
                total_row.get(
                    "custo_pendente",
                    0,
                )
                if total_row
                else 0
            ),
            "perc_entrega": (
                total_row.get(
                    "perc_entrega",
                    0,
                )
                if total_row
                else 0
            ),
        }

        return {
            "filters": filters.model_dump(
                mode="json"
            ),
            "count_remessas": len(
                remessas_rows
            ),
            "count_itens": len(itens),
            "remessas": remessas_rows,
            "resumo": resumo,
            "itens": itens,
        }

    @staticmethod
    def _build_projeto(
        projeto_rows: list[dict[str, Any]],
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Monta os dados básicos do projeto.

        O SankhyaQueryService normaliza os nomes
        das colunas para minúsculo, portanto:

        CODPROJ      -> codproj
        NOME_PROJETO -> nome_projeto
        """

        if not projeto_rows:
            return {
                "codproj": filters.codproj,
                "nome_projeto": (
                    f"Projeto {filters.codproj}"
                ),
            }

        projeto_row = projeto_rows[0]

        codproj_value = projeto_row.get(
            "codproj",
            filters.codproj,
        )

        nome_value = projeto_row.get(
            "nome_projeto"
        )

        try:
            codproj = int(codproj_value)
        except (
            TypeError,
            ValueError,
        ):
            codproj = filters.codproj

        nome_projeto = str(
            nome_value or ""
        ).strip()

        if not nome_projeto:
            nome_projeto = (
                f"Projeto {codproj}"
            )

        return {
            "codproj": codproj,
            "nome_projeto": nome_projeto,
        }

    @staticmethod
    def _get_definition(
        query_code: str,
    ) -> SankhyaQueryDefinition:
        definition = QUERY_REGISTRY.get(
            query_code
        )

        if definition is None:
            raise RuntimeError(
                f"A consulta obrigatória "
                f"'{query_code}' não está registrada."
            )

        return definition


def get_dashboard_service(
    query_service: SankhyaQueryService = Depends(
        get_sankhya_query_service
    ),
) -> DashboardService:
    return DashboardService(
        query_service=query_service
    )