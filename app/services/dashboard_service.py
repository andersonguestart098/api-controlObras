import asyncio
from typing import Any

from fastapi import Depends

from app.analytics.dashboard_analytics import (
    DashboardAnalytics,
)
from app.queries.registry import QUERY_REGISTRY
from app.schemas.filters import DashboardFilters
from app.schemas.projeto import ProjetoFiltroResponse
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

    async def listar_projetos_filtro(
        self,
    ) -> list[ProjetoFiltroResponse]:
        """
        Lista os projetos utilizados no Autocomplete
        da barra de filtros do dashboard.
        """

        definition = self._get_definition(
            "projetos_filtro"
        )

        # O execute_query exige DashboardFilters,
        # embora projetos_filtro.sql não utilize
        # CODPROJ nem período.
        filtros_neutros = DashboardFilters(
            codproj=1,
            dtneg_inicial=None,
            dtneg_final=None,
        )

        rows = await self._query_service.execute_query(
            definition,
            filtros_neutros,
        )

        projetos: list[ProjetoFiltroResponse] = []

        for row in rows:
            codproj_value = row.get("codproj")

            try:
                codproj = int(codproj_value)
            except (TypeError, ValueError):
                continue

            identificacao = self._normalizar_texto(
                row.get("identificacao")
            )

            abreviatura = self._normalizar_texto(
                row.get("abreviatura")
            )

            nome_projeto = (
                self._normalizar_texto(
                    row.get("nome_projeto")
                )
                or identificacao
                or abreviatura
                or f"Projeto {codproj}"
            )

            label_projeto = (
                self._normalizar_texto(
                    row.get("label_projeto")
                )
                or f"{codproj} - {nome_projeto}"
            )

            projetos.append(
                ProjetoFiltroResponse(
                    codproj=codproj,
                    identificacao=identificacao,
                    abreviatura=abreviatura,
                    nome_projeto=nome_projeto,
                    label_projeto=label_projeto,
                )
            )

        return projetos

    async def get_kpis(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Carrega os dados utilizados nos KPIs principais.

        Regras das remessas:

        - remessas.sql:
          notas-mãe TOP 1009, representando a
          Remessa futura/faturamento.

          Traz também o custo próprio da nota,
          calculado no cabeçalho.

        - remessas_transporte.sql:
          notas-filhas TOP 1157, representando
          valor transportado, impostos e custo
          efetivamente entregue.

        - itens_remessas.sql:
          não é utilizado nos KPIs.
          Permanece apenas no controle detalhado
          de remessas.
        """

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

        devolucoes_interno_obras_definition = (
            self._get_definition(
                "devolucoes_interno_obras"
            )
        )

        remessas_definition = self._get_definition(
            "remessas"
        )

        remessas_transporte_definition = (
            self._get_definition(
                "remessas_transporte"
            )
        )

        notas_impostos_definition = (
            self._get_definition(
                "notas_impostos"
            )
        )

        pagamentos_definition = self._get_definition(
            "pagamentos"
        )

        compras_definition = self._get_definition(
            "compras"
        )

        bonificados_definition = self._get_definition(
            "bonificados"
        )

        mao_de_obra_definition = self._get_definition(
            "mao_de_obra"
        )

        despesas_gerais_definition = (
            self._get_definition(
                "despesas_gerais"
            )
        )

        (
            projeto_rows,
            notas_rows,
            itens_notas_rows,
            interno_obras_rows,
            devolucoes_interno_obras_rows,
            remessas_rows,
            remessas_transporte_rows,
            notas_impostos_rows,
            compras_rows,
            bonificados_rows,
            mao_de_obra_rows,
            pagamentos_rows,
            despesas_gerais_rows,
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
                devolucoes_interno_obras_definition,
                filters,
            ),

            self._query_service.execute_query(
                remessas_definition,
                filters,
            ),

            self._query_service.execute_query(
                remessas_transporte_definition,
                filters,
            ),

            self._query_service.execute_query(
                notas_impostos_definition,
                filters,
            ),

            self._query_service.execute_query(
                compras_definition,
                filters,
            ),

            self._query_service.execute_query(
                bonificados_definition,
                filters,
            ),

            self._query_service.execute_query(
                mao_de_obra_definition,
                filters,
            ),

            self._query_service.execute_query(
                pagamentos_definition,
                filters,
            ),

            self._query_service.execute_query(
                despesas_gerais_definition,
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

            devolucoes_interno_obras=(
                devolucoes_interno_obras_rows
            ),

            remessas=remessas_rows,

            remessas_transporte=(
                remessas_transporte_rows
            ),

            notas_impostos=notas_impostos_rows,
            compras=compras_rows,
            bonificados=bonificados_rows,
            mao_de_obra=mao_de_obra_rows,
            pagamentos=pagamentos_rows,
            despesas_gerais=despesas_gerais_rows,
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
        """
        Carrega todas as consultas registradas.

        Este endpoint continua incluindo
        itens_remessas, pois é um endpoint
        geral para inspeção dos dados brutos.
        """

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

    async def get_movimentos(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        movimentos_definition = self._get_definition(
            "movimentos"
        )

        movimentos_rows = (
            await self._query_service.execute_query(
                movimentos_definition,
                filters,
            )
        )

        return {
            "filters": filters.model_dump(
                mode="json"
            ),
            "count": len(movimentos_rows),
            "movimentos": movimentos_rows,
        }

    async def get_pagamentos(
            self,
            filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Retorna os títulos financeiros detalhados
        vinculados à obra.

        Essa carga é separada dos KPIs e será usada
        para listagem e tooltip no frontend.
        """

        pagamentos_definition = self._get_definition(
            "pagamentos"
        )

        pagamentos_rows = (
            await self._query_service.execute_query(
                pagamentos_definition,
                filters,
            )
        )

        return {
            "filters": filters.model_dump(
                mode="json"
            ),

            "count": len(pagamentos_rows),

            "pagamentos": pagamentos_rows,
        }

    async def get_despesas_gerais(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Retorna as despesas gerais detalhadas
        vinculadas ao projeto.

        A carga é separada dos KPIs para permitir
        listagem e tooltip no frontend sem alterar
        o formato do restante do dashboard.
        """

        despesas_definition = self._get_definition(
            "despesas_gerais"
        )

        despesas_rows = (
            await self._query_service.execute_query(
                despesas_definition,
                filters,
            )
        )

        return {
            "filters": filters.model_dump(
                mode="json"
            ),

            "count": len(despesas_rows),

            "despesas": despesas_rows,
        }

    async def get_remessas_control(
        self,
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Controle detalhado das remessas.

        Aqui o itens_remessas continua sendo
        utilizado para calcular:

        - quantidade total;
        - quantidade entregue;
        - quantidade pendente;
        - valor entregue;
        - valor pendente;
        - custo entregue;
        - custo pendente;
        - percentual de entrega.
        """

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

    async def get_compras_detalhes(
            self,
            filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Retorna os pedidos de compra com seus materiais
        aninhados.

        Essa consulta é separada dos KPIs para evitar
        carregar todos os itens em cada atualização do
        dashboard.
        """

        definition = self._get_definition(
            "compras_itens"
        )

        rows = await self._query_service.execute_query(
            definition,
            filters,
        )

        compras_por_nunota: dict[
            Any,
            dict[str, Any],
        ] = {}

        for row in rows:
            nunota = row.get("nunota")

            if nunota is None:
                continue

            compra = compras_por_nunota.setdefault(
                nunota,
                {
                    "nunota": nunota,
                    "numnota": row.get("numnota"),
                    "dtneg": row.get("dtneg"),

                    "codproj": row.get("codproj"),
                    "projeto": row.get("projeto"),

                    "codparc": row.get("codparc"),
                    "parceiro": row.get("parceiro"),
                    "cgc_cpf": row.get("cgc_cpf"),

                    "codtipoper": row.get(
                        "codtipoper"
                    ),
                    "descroper": row.get(
                        "descroper"
                    ),
                    "tipo_movimento": row.get(
                        "tipo_movimento"
                    ),

                    "codtipvenda": row.get(
                        "codtipvenda"
                    ),
                    "tipo_negociacao": row.get(
                        "tipo_negociacao"
                    ),

                    "vlrnota": row.get(
                        "vlrnota",
                        0,
                    ),
                    "vlricms": row.get(
                        "vlricms",
                        0,
                    ),
                    "vlrpis": row.get(
                        "vlrpis",
                        0,
                    ),
                    "vlrcofins": row.get(
                        "vlrcofins",
                        0,
                    ),

                    "itens": [],
                },
            )

            compra["itens"].append(
                {
                    "sequencia": row.get(
                        "sequencia"
                    ),
                    "codprod": row.get(
                        "codprod"
                    ),
                    "descrprod": row.get(
                        "descrprod"
                    ),
                    "unidade": row.get(
                        "unidade"
                    ),
                    "controle": row.get(
                        "controle"
                    ),

                    "qtdneg": row.get(
                        "qtdneg",
                        0,
                    ),
                    "vlrunit": row.get(
                        "vlrunit",
                        0,
                    ),
                    "vlrtot": row.get(
                        "vlrtot",
                        0,
                    ),
                    "vlrdesc": row.get(
                        "vlrdesc",
                        0,
                    ),
                    "vlr_item_liquido": row.get(
                        "vlr_item_liquido",
                        0,
                    ),

                    "cussemicm": row.get(
                        "cussemicm",
                        0,
                    ),
                    "custo_total_item": row.get(
                        "custo_total_item",
                        0,
                    ),
                }
            )

        compras = list(
            compras_por_nunota.values()
        )

        return {
            "filters": filters.model_dump(
                mode="json"
            ),
            "count_compras": len(compras),
            "count_itens": len(rows),
            "compras": compras,
        }

    @staticmethod
    def _build_projeto(
        projeto_rows: list[dict[str, Any]],
        filters: DashboardFilters,
    ) -> dict[str, Any]:
        """
        Monta os dados básicos do projeto.

        O SankhyaQueryService normaliza os nomes
        das colunas para minúsculo:

        CODPROJ       -> codproj
        NOME_PROJETO  -> nome_projeto
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
    def _normalizar_texto(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        texto = str(value).strip()

        return texto or None

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