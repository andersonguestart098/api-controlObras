import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import ceil
from time import monotonic, perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from app.integrations.vexpenses_client import (
    VExpensesClient,
    get_vexpenses_client,
)


logger = logging.getLogger(__name__)


class VExpensesService:
    """
    Regras de integração e consulta da VExpenses.

    O client cuida da comunicação HTTP.
    Este service decide:
    - quais endpoints chamar;
    - quais parâmetros enviar;
    - quais dados relacionados incluir;
    - como normalizar os dados para o dashboard.

    Otimizações aplicadas ao resumo:
    - usa o ano atual quando o dashboard não informa datas;
    - filtra os relatórios por approval_date na própria VExpenses;
    - filtra o projeto localmente pelo course_id da despesa;
    - evita carregar rateios quando incluir_movimentos=False;
    - reutiliza relatórios em cache por alguns minutos;
    - carrega páginas em paralelo quando a API informa a paginação;
    - reutiliza o projeto encontrado pelo integration_id.
    """

    REPORT_SUMMARY_INCLUDES = ",".join(
        [
            "expenses",
            "user",
            "expenses.costs_center",
            "expenses.expense_type",
            "expenses.payment_method",
        ]
    )

    REPORT_DETAIL_INCLUDES = ",".join(
        [
            REPORT_SUMMARY_INCLUDES,
            "expenses.apportionment",
        ]
    )

    REPORTS_CACHE_TTL_SECONDS = 300.0
    PROJECT_CACHE_TTL_SECONDS = 900.0
    MAX_CONCURRENT_PAGES = 4
    MAX_PAGES = 100
    TIMEZONE = ZoneInfo("America/Sao_Paulo")

    def __init__(
        self,
        client: VExpensesClient,
    ) -> None:
        self._client = client

        # Chave:
        # (data_inicial, data_final, incluir_rateios)
        self._reports_cache: dict[
            tuple[date, date, bool],
            tuple[float, list[dict[str, Any]]],
        ] = {}
        self._reports_cache_lock = asyncio.Lock()

        # Cache do projeto já normalizado para o dashboard.
        self._project_by_id_cache: dict[
            int,
            tuple[float, dict[str, Any]],
        ] = {}
        self._project_by_integration_cache: dict[
            str,
            tuple[float, dict[str, Any]],
        ] = {}

    async def listar_projetos(
        self,
        *,
        pagina: int = 1,
        itens_por_pagina: int = 100,
    ) -> Any:
        """
        Lista os projetos cadastrados na VExpenses.
        """

        params = self._montar_paginacao(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
        )

        return await self._client.get(
            "projects",
            params=params,
        )

    async def buscar_projeto_por_id(
        self,
        project_id: int,
    ) -> Any:
        """
        Busca um projeto específico pelo ID da VExpenses.

        Este método preserva a resposta original da API para a
        rota pública /projects/{project_id}.
        """

        if project_id <= 0:
            raise ValueError(
                "O ID do projeto deve ser maior que zero."
            )

        return await self._client.get(
            f"projects/{project_id}",
        )

    async def listar_relatorios_aprovados(
        self,
        *,
        pagina: int = 1,
        itens_por_pagina: int = 50,
        data_inicial: date | None = None,
        data_final: date | None = None,
        incluir_rateios: bool = True,
    ) -> Any:
        """
        Lista relatórios aprovados com suas despesas e relações.

        Quando o período é informado, ele é aplicado sobre
        approval_date pela própria API VExpenses.

        incluir_rateios=False reduz o payload do resumo quando a
        lista completa de movimentos não será devolvida.
        """

        self._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        includes = (
            self.REPORT_DETAIL_INCLUDES
            if incluir_rateios
            else self.REPORT_SUMMARY_INCLUDES
        )

        params: dict[str, Any] = {
            **self._montar_paginacao(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
            ),
            "include": includes,
        }

        if data_inicial is not None and data_final is not None:
            params["search"] = (
                "approval_date:"
                f"{data_inicial.isoformat()},"
                f"{data_final.isoformat()}"
            )
            params["searchFields"] = "approval_date:between"

        return await self._client.get(
            "reports/status/APROVADO",
            params=params,
        )

    async def obter_resumo_dashboard(
        self,
        *,
        project_id: int,
        data_inicial: date | None = None,
        data_final: date | None = None,
        incluir_movimentos: bool = False,
    ) -> dict[str, Any]:
        """
        Retorna o resumo das despesas aprovadas vinculadas ao projeto.

        Regras:
        - o projeto é comparado com course_id de cada despesa;
        - sem datas informadas, usa 01/01 do ano atual até hoje;
        - o filtro enviado à VExpenses usa approval_date;
        - após receber os relatórios, o service também valida a data
          real da despesa e o course_id do projeto.
        """

        inicio = perf_counter()

        if project_id <= 0:
            raise ValueError(
                "O ID do projeto deve ser maior que zero."
            )

        data_inicial, data_final = self._resolver_periodo_dashboard(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        # O projeto costuma estar em cache porque o frontend consulta
        # primeiro /projects/by-integration/{codproj}.
        projeto_task = self._obter_projeto_normalizado(
            project_id=project_id,
        )

        relatorios_task = self._listar_todos_relatorios_aprovados(
            data_inicial=data_inicial,
            data_final=data_final,
            incluir_rateios=incluir_movimentos,
        )

        projeto, relatorios = await asyncio.gather(
            projeto_task,
            relatorios_task,
        )

        movimentos = self._normalizar_movimentos(
            relatorios=relatorios,
            project_id=project_id,
            data_inicial=data_inicial,
            data_final=data_final,
        )

        resposta = self._montar_resumo(
            movimentos=movimentos,
            projeto=projeto,
            data_inicial=data_inicial,
            data_final=data_final,
            incluir_movimentos=incluir_movimentos,
        )

        logger.info(
            "VExpenses summary concluído. "
            "project_id=%s periodo=%s..%s relatorios=%s "
            "movimentos=%s incluir_movimentos=%s tempo=%.3fs",
            project_id,
            data_inicial.isoformat(),
            data_final.isoformat(),
            len(relatorios),
            len(movimentos),
            incluir_movimentos,
            perf_counter() - inicio,
        )

        return resposta

    async def _listar_todos_relatorios_aprovados(
        self,
        *,
        data_inicial: date,
        data_final: date,
        incluir_rateios: bool,
    ) -> list[dict[str, Any]]:
        """
        Busca todas as páginas de relatórios aprovados do período.

        O filtro de período é executado pela VExpenses sobre
        approval_date. O filtro de course_id continua sendo aplicado
        localmente porque ele está dentro de cada despesa.
        """

        cache_key = (
            data_inicial,
            data_final,
            incluir_rateios,
        )

        cached = self._get_reports_cache(cache_key)

        if cached is not None:
            logger.info(
                "VExpenses relatórios obtidos do cache. "
                "periodo=%s..%s incluir_rateios=%s quantidade=%s",
                data_inicial.isoformat(),
                data_final.isoformat(),
                incluir_rateios,
                len(cached),
            )
            return cached

        # Evita duas requisições simultâneas carregarem o mesmo
        # conjunto de relatórios quando o React dispara refetch.
        async with self._reports_cache_lock:
            cached = self._get_reports_cache(cache_key)

            if cached is not None:
                return cached

            itens_por_pagina = 100

            primeira_resposta = await self.listar_relatorios_aprovados(
                pagina=1,
                itens_por_pagina=itens_por_pagina,
                data_inicial=data_inicial,
                data_final=data_final,
                incluir_rateios=incluir_rateios,
            )

            primeira_pagina = self._extrair_dados_pagina(
                primeira_resposta
            )

            relatorios = list(primeira_pagina)

            ultima_pagina = self._extrair_ultima_pagina(
                resposta=primeira_resposta,
                itens_por_pagina=itens_por_pagina,
            )

            if ultima_pagina is not None:
                ultima_pagina = min(
                    ultima_pagina,
                    self.MAX_PAGES,
                )

                if ultima_pagina > 1:
                    outras_paginas = (
                        await self._carregar_paginas_em_paralelo(
                            pagina_inicial=2,
                            pagina_final=ultima_pagina,
                            itens_por_pagina=itens_por_pagina,
                            data_inicial=data_inicial,
                            data_final=data_final,
                            incluir_rateios=incluir_rateios,
                        )
                    )

                    for dados_pagina in outras_paginas:
                        relatorios.extend(dados_pagina)

            elif len(primeira_pagina) == itens_por_pagina:
                # Fallback para APIs que não informam total de páginas.
                pagina = 2

                while pagina <= self.MAX_PAGES:
                    resposta = await self.listar_relatorios_aprovados(
                        pagina=pagina,
                        itens_por_pagina=itens_por_pagina,
                        data_inicial=data_inicial,
                        data_final=data_final,
                        incluir_rateios=incluir_rateios,
                    )

                    dados_pagina = self._extrair_dados_pagina(
                        resposta
                    )

                    relatorios.extend(dados_pagina)

                    if len(dados_pagina) < itens_por_pagina:
                        break

                    pagina += 1

            self._set_reports_cache(
                key=cache_key,
                relatorios=relatorios,
            )

            return relatorios

    async def buscar_projeto_por_codproj(
        self,
        *,
        codproj: int,
    ) -> dict[str, Any]:
        """
        Busca um projeto da VExpenses pelo integration_id,
        utilizando o CODPROJ do Sankhya.
        """

        if codproj <= 0:
            raise ValueError(
                "O código do projeto deve ser maior que zero."
            )

        integration_id_procurado = str(codproj).strip()

        cached = self._get_project_by_integration_cache(
            integration_id_procurado
        )

        if cached is not None:
            return cached

        pagina = 1
        itens_por_pagina = 100

        while True:
            resposta = await self.listar_projetos(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
            )

            projetos = (
                resposta.get("data", [])
                if isinstance(resposta, dict)
                else []
            )

            if not isinstance(projetos, list):
                break

            for projeto_original in projetos:
                if not isinstance(projeto_original, dict):
                    continue

                integration_id = str(
                    projeto_original.get("integration_id") or ""
                ).strip()

                projeto = self._normalizar_projeto_integracao(
                    projeto_original
                )

                # Aproveita a paginação para preencher cache de outros
                # projetos e acelerar consultas futuras do dashboard.
                if integration_id:
                    self._set_project_cache(projeto)

                if integration_id == integration_id_procurado:
                    return projeto

            if len(projetos) < itens_por_pagina:
                break

            pagina += 1

            if pagina > self.MAX_PAGES:
                break

        raise ValueError(
            "Nenhum projeto da VExpenses foi encontrado "
            f"com integration_id igual a {codproj}."
        )

    async def _obter_projeto_normalizado(
        self,
        *,
        project_id: int,
    ) -> dict[str, Any]:
        cached = self._get_project_by_id_cache(project_id)

        if cached is not None:
            return cached

        resposta = await self.buscar_projeto_por_id(
            project_id=project_id,
        )

        projeto = self._normalizar_projeto(
            resposta=resposta,
            project_id=project_id,
        )

        self._set_project_cache(projeto)

        return projeto

    async def _carregar_paginas_em_paralelo(
        self,
        *,
        pagina_inicial: int,
        pagina_final: int,
        itens_por_pagina: int,
        data_inicial: date,
        data_final: date,
        incluir_rateios: bool,
    ) -> list[list[dict[str, Any]]]:
        semaphore = asyncio.Semaphore(
            self.MAX_CONCURRENT_PAGES
        )

        async def carregar_pagina(
            pagina: int,
        ) -> list[dict[str, Any]]:
            async with semaphore:
                resposta = await self.listar_relatorios_aprovados(
                    pagina=pagina,
                    itens_por_pagina=itens_por_pagina,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    incluir_rateios=incluir_rateios,
                )

                return self._extrair_dados_pagina(
                    resposta
                )

        return await asyncio.gather(
            *[
                carregar_pagina(pagina)
                for pagina in range(
                    pagina_inicial,
                    pagina_final + 1,
                )
            ]
        )

    def _normalizar_movimentos(
        self,
        *,
        relatorios: list[dict[str, Any]],
        project_id: int,
        data_inicial: date | None,
        data_final: date | None,
    ) -> list[dict[str, Any]]:
        """
        Transforma os relatórios em uma lista plana de despesas,
        mantendo somente aquelas cujo course_id corresponde ao
        projeto solicitado.

        Cada despesa entra uma única vez. Os rateios são mantidos
        apenas como informação de detalhamento e não multiplicam
        o valor da despesa.
        """

        movimentos: list[dict[str, Any]] = []

        for relatorio in relatorios:
            usuario = self._extrair_data_relacionada(
                relatorio.get("user")
            )

            despesas = self._extrair_lista_relacionada(
                relatorio.get("expenses")
            )

            for despesa in despesas:
                if not self._ids_iguais(
                    despesa.get("course_id"),
                    project_id,
                ):
                    continue

                data_despesa = self._parse_date(
                    despesa.get("date")
                )

                if not self._data_dentro_periodo(
                    data_movimento=data_despesa,
                    data_inicial=data_inicial,
                    data_final=data_final,
                ):
                    continue

                valor_original = self._to_decimal(
                    despesa.get("converted_value")
                    if despesa.get("converted_value") is not None
                    else despesa.get("value")
                )

                tipo_despesa = self._extrair_data_relacionada(
                    despesa.get("expense_type")
                )

                centro_custo = self._extrair_data_relacionada(
                    despesa.get("costs_center")
                )

                forma_pagamento = self._extrair_data_relacionada(
                    despesa.get("payment_method")
                )

                rateios = self._normalizar_rateios(
                    despesa.get("apportionment")
                )

                movimentos.append(
                    {
                        "project_id": project_id,
                        "course_id": despesa.get("course_id"),
                        "report_id": relatorio.get("id"),
                        "report_description": relatorio.get(
                            "description"
                        ),
                        "report_status": relatorio.get("status"),
                        "approval_date": relatorio.get(
                            "approval_date"
                        ),
                        "payment_date": relatorio.get(
                            "payment_date"
                        ),
                        "pdf_link": relatorio.get("pdf_link"),
                        "excel_link": relatorio.get("excel_link"),
                        "expense_id": despesa.get("id"),
                        "expense_date": (
                            data_despesa.isoformat()
                            if data_despesa is not None
                            else None
                        ),
                        "expense_title": despesa.get("title"),
                        "expense_observation": despesa.get(
                            "observation"
                        ),
                        "receipt_url": despesa.get("reicept_url"),
                        "user_id": usuario.get("id"),
                        "user_name": usuario.get("name"),
                        "user_email": usuario.get("email"),
                        "expense_type_id": tipo_despesa.get("id"),
                        "expense_type": tipo_despesa.get(
                            "description"
                        ),
                        "cost_center_id": centro_custo.get("id"),
                        "cost_center_integration_id": (
                            centro_custo.get("integration_id")
                        ),
                        "cost_center": centro_custo.get("name"),
                        "payment_method_id": forma_pagamento.get(
                            "id"
                        ),
                        "payment_method": forma_pagamento.get(
                            "description"
                        ),
                        "reimbursable": bool(
                            despesa.get("reimbursable")
                        ),
                        "currency": (
                            despesa.get("converted_currency_iso")
                            or despesa.get("original_currency_iso")
                            or "BRL"
                        ),
                        "original_value": self._money_decimal(
                            valor_original
                        ),
                        "value": self._money_decimal(
                            valor_original
                        ),
                        "apportionments": rateios,
                    }
                )

        return movimentos

    def _montar_resumo(
        self,
        *,
        movimentos: list[dict[str, Any]],
        projeto: dict[str, Any],
        data_inicial: date | None,
        data_final: date | None,
        incluir_movimentos: bool = False,
    ) -> dict[str, Any]:
        """
        Monta KPIs e agrupamentos do projeto sem devolver a lista
        completa de movimentos por padrão.
        """

        total = sum(
            (
                self._to_decimal(movimento.get("value"))
                for movimento in movimentos
            ),
            Decimal("0"),
        )

        total_reembolsavel = sum(
            (
                self._to_decimal(movimento.get("value"))
                for movimento in movimentos
                if movimento.get("reimbursable") is True
            ),
            Decimal("0"),
        )

        total_nao_reembolsavel = total - total_reembolsavel

        despesas_ids = {
            movimento.get("expense_id")
            for movimento in movimentos
            if movimento.get("expense_id") is not None
        }

        relatorios_ids = {
            movimento.get("report_id")
            for movimento in movimentos
            if movimento.get("report_id") is not None
        }

        quantidade_despesas = len(despesas_ids)

        media = (
            total / Decimal(quantidade_despesas)
            if quantidade_despesas > 0
            else Decimal("0")
        )

        resposta: dict[str, Any] = {
            "project": projeto,
            "filters": {
                "project_id": projeto.get("id"),
                "data_inicial": (
                    data_inicial.isoformat()
                    if data_inicial is not None
                    else None
                ),
                "data_final": (
                    data_final.isoformat()
                    if data_final is not None
                    else None
                ),
            },
            "summary": {
                "total_aprovado": self._money_decimal(total),
                "quantidade_despesas": quantidade_despesas,
                "quantidade_relatorios": len(relatorios_ids),
                "media_por_despesa": self._money_decimal(media),
                "total_reembolsavel": self._money_decimal(
                    total_reembolsavel
                ),
                "total_nao_reembolsavel": self._money_decimal(
                    total_nao_reembolsavel
                ),
            },
            "por_tipo_despesa": self._agrupar_movimentos(
                movimentos,
                campo="expense_type",
            ),
            "por_centro_custo": self._agrupar_movimentos(
                movimentos,
                campo="cost_center",
            ),
            "por_forma_pagamento": self._agrupar_movimentos(
                movimentos,
                campo="payment_method",
            ),
            "por_usuario": self._agrupar_movimentos(
                movimentos,
                campo="user_name",
            ),
        }

        if incluir_movimentos:
            resposta["movimentos"] = movimentos

        return resposta

    def _agrupar_movimentos(
        self,
        movimentos: list[dict[str, Any]],
        *,
        campo: str,
    ) -> list[dict[str, Any]]:
        agrupamentos: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total": Decimal("0"),
                "quantidade": 0,
            }
        )

        for movimento in movimentos:
            descricao = str(
                movimento.get(campo) or "Não informado"
            ).strip()

            agrupamentos[descricao]["total"] += self._to_decimal(
                movimento.get("value")
            )
            agrupamentos[descricao]["quantidade"] += 1

        resultado = [
            {
                "description": descricao,
                "total": self._money_decimal(dados["total"]),
                "quantidade": dados["quantidade"],
            }
            for descricao, dados in agrupamentos.items()
        ]

        resultado.sort(
            key=lambda item: item["total"],
            reverse=True,
        )

        return resultado

    def _get_reports_cache(
        self,
        key: tuple[date, date, bool],
    ) -> list[dict[str, Any]] | None:
        cached = self._reports_cache.get(key)

        if cached is None:
            return None

        expires_at, relatorios = cached

        if monotonic() >= expires_at:
            self._reports_cache.pop(key, None)
            return None

        return relatorios

    def _set_reports_cache(
        self,
        *,
        key: tuple[date, date, bool],
        relatorios: list[dict[str, Any]],
    ) -> None:
        self._reports_cache[key] = (
            monotonic() + self.REPORTS_CACHE_TTL_SECONDS,
            relatorios,
        )

    def _get_project_by_id_cache(
        self,
        project_id: int,
    ) -> dict[str, Any] | None:
        return self._get_project_cache_value(
            self._project_by_id_cache,
            project_id,
        )

    def _get_project_by_integration_cache(
        self,
        integration_id: str,
    ) -> dict[str, Any] | None:
        return self._get_project_cache_value(
            self._project_by_integration_cache,
            integration_id,
        )

    @staticmethod
    def _get_project_cache_value(
        cache: dict[Any, tuple[float, dict[str, Any]]],
        key: Any,
    ) -> dict[str, Any] | None:
        cached = cache.get(key)

        if cached is None:
            return None

        expires_at, projeto = cached

        if monotonic() >= expires_at:
            cache.pop(key, None)
            return None

        return projeto

    def _set_project_cache(
        self,
        projeto: dict[str, Any],
    ) -> None:
        expires_at = monotonic() + self.PROJECT_CACHE_TTL_SECONDS

        project_id = projeto.get("id")
        integration_id = str(
            projeto.get("integration_id") or ""
        ).strip()

        try:
            normalized_project_id = int(project_id)
        except (TypeError, ValueError):
            normalized_project_id = None

        if normalized_project_id is not None:
            self._project_by_id_cache[normalized_project_id] = (
                expires_at,
                projeto,
            )

        if integration_id:
            self._project_by_integration_cache[integration_id] = (
                expires_at,
                projeto,
            )

    @staticmethod
    def _extrair_dados_pagina(
        resposta: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(resposta, dict):
            return []

        dados = resposta.get("data", [])

        if not isinstance(dados, list):
            return []

        return [
            item
            for item in dados
            if isinstance(item, dict)
        ]

    @staticmethod
    def _extrair_ultima_pagina(
        *,
        resposta: Any,
        itens_por_pagina: int,
    ) -> int | None:
        if not isinstance(resposta, dict):
            return None

        meta = resposta.get("meta")
        pagination = resposta.get("pagination")

        meta_pagination = (
            meta.get("pagination")
            if isinstance(meta, dict)
            else None
        )

        containers = [
            resposta,
            meta,
            pagination,
            meta_pagination,
        ]

        for container in containers:
            if not isinstance(container, dict):
                continue

            for campo in (
                "last_page",
                "total_pages",
                "totalPages",
            ):
                valor = container.get(campo)

                try:
                    if valor is not None:
                        return max(int(valor), 1)
                except (TypeError, ValueError):
                    continue

        for container in containers:
            if not isinstance(container, dict):
                continue

            total = container.get("total")

            try:
                if total is not None:
                    return max(
                        ceil(int(total) / itens_por_pagina),
                        1,
                    )
            except (TypeError, ValueError):
                continue

        return None

    @classmethod
    def _resolver_periodo_dashboard(
        cls,
        *,
        data_inicial: date | None,
        data_final: date | None,
    ) -> tuple[date, date]:
        cls._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        if data_inicial is not None and data_final is not None:
            return data_inicial, data_final

        hoje = datetime.now(cls.TIMEZONE).date()

        return date(hoje.year, 1, 1), hoje

    @staticmethod
    def _normalizar_projeto_integracao(
        projeto: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": projeto.get("id"),
            "name": projeto.get("name"),
            "company_name": projeto.get("company_name"),
            "integration_id": str(
                projeto.get("integration_id") or ""
            ).strip(),
            "on": projeto.get("on"),
        }

    @staticmethod
    def _normalizar_projeto(
        *,
        resposta: Any,
        project_id: int,
    ) -> dict[str, Any]:
        """
        Normaliza projects/{id}, com ou sem envelope data.
        """

        if not isinstance(resposta, dict):
            return {
                "id": project_id,
                "integration_id": None,
                "description": None,
                "name": None,
            }

        dados = resposta.get("data")
        projeto = dados if isinstance(dados, dict) else resposta

        descricao = (
            projeto.get("description")
            or projeto.get("name")
        )

        return {
            "id": projeto.get("id", project_id),
            "integration_id": projeto.get("integration_id"),
            "description": descricao,
            "name": descricao,
            "company_name": projeto.get("company_name"),
            "on": projeto.get("on"),
        }

    @classmethod
    def _normalizar_rateios(
        cls,
        valor: Any,
    ) -> list[dict[str, Any]]:
        rateios = cls._extrair_lista_relacionada(valor)

        return [
            {
                "id": rateio.get("id"),
                "integration_id": rateio.get("integration_id"),
                "description": rateio.get("description"),
                "percentage": cls._to_float(
                    rateio.get("percentage")
                ),
            }
            for rateio in rateios
        ]

    @staticmethod
    def _extrair_data_relacionada(
        valor: Any,
    ) -> dict[str, Any]:
        if not isinstance(valor, dict):
            return {}

        dados = valor.get("data")
        return dados if isinstance(dados, dict) else {}

    @staticmethod
    def _extrair_lista_relacionada(
        valor: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(valor, dict):
            return []

        dados = valor.get("data")
        return dados if isinstance(dados, list) else []

    @staticmethod
    def _ids_iguais(
        primeiro: Any,
        segundo: Any,
    ) -> bool:
        if primeiro is None or segundo is None:
            return False

        return str(primeiro).strip() == str(segundo).strip()

    @staticmethod
    def _parse_date(
        valor: Any,
    ) -> date | None:
        if valor is None:
            return None

        texto = str(valor).strip()

        if not texto:
            return None

        try:
            return datetime.fromisoformat(texto).date()
        except ValueError:
            return None

    @staticmethod
    def _data_dentro_periodo(
        *,
        data_movimento: date | None,
        data_inicial: date | None,
        data_final: date | None,
    ) -> bool:
        if data_inicial is None or data_final is None:
            return True

        if data_movimento is None:
            return False

        return data_inicial <= data_movimento <= data_final

    @staticmethod
    def _to_decimal(
        valor: Any,
    ) -> Decimal:
        if valor is None:
            return Decimal("0")

        try:
            return Decimal(str(valor))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            return Decimal("0")

    @classmethod
    def _to_float(
        cls,
        valor: Any,
    ) -> float:
        return float(cls._to_decimal(valor))

    @staticmethod
    def _money_decimal(
        valor: Decimal,
    ) -> float:
        return float(
            valor.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )

    @staticmethod
    def _montar_paginacao(
        *,
        pagina: int,
        itens_por_pagina: int,
    ) -> dict[str, Any]:
        if pagina < 1:
            raise ValueError(
                "A página deve ser maior ou igual a 1."
            )

        if itens_por_pagina < 1:
            raise ValueError(
                "A quantidade de itens por página "
                "deve ser maior que zero."
            )

        if itens_por_pagina > 100:
            raise ValueError(
                "A quantidade máxima é de 100 itens por página."
            )

        return {
            "paginate": "true",
            "page": pagina,
            "per_page": itens_por_pagina,
        }

    @staticmethod
    def _validar_periodo(
        *,
        data_inicial: date | None,
        data_final: date | None,
    ) -> None:
        apenas_uma_data_informada = (
            data_inicial is None
        ) != (
            data_final is None
        )

        if apenas_uma_data_informada:
            raise ValueError(
                "Informe data_inicial e data_final juntas."
            )

        if (
            data_inicial is not None
            and data_final is not None
            and data_inicial > data_final
        ):
            raise ValueError(
                "data_inicial não pode ser maior que data_final."
            )


_vexpenses_service: VExpensesService | None = None


def get_vexpenses_service() -> VExpensesService:
    """
    Retorna uma única instância do service por processo.

    Isso mantém os caches de projetos e relatórios entre as
    requisições atendidas pelo mesmo dyno/processo.
    """

    global _vexpenses_service

    if _vexpenses_service is None:
        _vexpenses_service = VExpensesService(
            client=get_vexpenses_client(),
        )

    return _vexpenses_service