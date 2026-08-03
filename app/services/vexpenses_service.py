from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.integrations.vexpenses_client import (
    VExpensesClient,
    get_vexpenses_client,
)


class VExpensesService:
    """
    Regras de integração e consulta da VExpenses.

    O client cuida da comunicação HTTP.
    Este service decide:
    - quais endpoints chamar;
    - quais parâmetros enviar;
    - quais dados relacionados incluir;
    - como normalizar os dados para o dashboard.
    """

    REPORT_INCLUDES = ",".join(
        [
            "expenses",
            "user",
            "expenses.costs_center",
            "expenses.expense_type",
            "expenses.payment_method",
            "expenses.apportionment",
        ]
    )

    def __init__(
        self,
        client: VExpensesClient,
    ) -> None:
        self._client = client

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
    ) -> Any:
        """
        Lista relatórios aprovados com suas despesas,
        usuário, centro de custo, tipo, pagamento e rateio.

        Neste endpoint bruto, o período informado é aplicado
        sobre approval_date pela própria API da VExpenses.
        """

        self._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        params: dict[str, Any] = {
            **self._montar_paginacao(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
            ),
            "include": self.REPORT_INCLUDES,
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
        Retorna o resumo das despesas aprovadas vinculadas
        a um projeto específico da VExpenses.

        O vínculo do projeto é feito pelo course_id existente
        em cada despesa retornada pela VExpenses.

        O período é aplicado sobre a data da despesa.
        """

        if project_id <= 0:
            raise ValueError(
                "O ID do projeto deve ser maior que zero."
            )

        self._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        resposta_projeto = await self.buscar_projeto_por_id(
            project_id=project_id,
        )

        projeto = self._normalizar_projeto(
            resposta=resposta_projeto,
            project_id=project_id,
        )

        relatorios = await self._listar_todos_relatorios_aprovados()

        movimentos = self._normalizar_movimentos(
            relatorios=relatorios,
            project_id=project_id,
            data_inicial=data_inicial,
            data_final=data_final,
        )

        return self._montar_resumo(
            movimentos=movimentos,
            projeto=projeto,
            data_inicial=data_inicial,
            data_final=data_final,
            incluir_movimentos=incluir_movimentos,
        )

    async def _listar_todos_relatorios_aprovados(
        self,
    ) -> list[dict[str, Any]]:
        """
        Percorre todas as páginas de relatórios aprovados.

        Não aplica o período de aprovação aqui porque o resumo
        deve filtrar pela data real da despesa. Uma despesa pode
        ter sido realizada em uma data e aprovada posteriormente.
        """

        pagina = 1
        itens_por_pagina = 100
        relatorios: list[dict[str, Any]] = []

        while True:
            resposta = await self.listar_relatorios_aprovados(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
            )

            if not isinstance(resposta, dict):
                break

            dados_pagina = resposta.get("data", [])

            if not isinstance(dados_pagina, list):
                break

            relatorios.extend(dados_pagina)

            if len(dados_pagina) < itens_por_pagina:
                break

            pagina += 1

            # Proteção para evitar loop infinito caso a API
            # retorne paginação inconsistente.
            if pagina > 100:
                break

        return relatorios

    async def buscar_projeto_por_codproj(
            self,
            *,
            codproj: int,
    ) -> dict[str, Any]:
        """
        Busca um projeto da VExpenses pelo código
        de integração, utilizando o CODPROJ do Sankhya.
        """

        if codproj <= 0:
            raise ValueError(
                "O código do projeto deve ser maior que zero."
            )

        pagina = 1
        itens_por_pagina = 100

        while True:
            resposta = await self.listar_projetos(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
            )

            projetos = resposta.get("data", [])

            if not isinstance(projetos, list):
                break

            for projeto in projetos:
                integration_id = str(
                    projeto.get("integration_id") or ""
                ).strip()

                if integration_id == str(codproj):
                    return {
                        "id": projeto.get("id"),
                        "name": projeto.get("name"),
                        "company_name": projeto.get(
                            "company_name"
                        ),
                        "integration_id": integration_id,
                        "on": projeto.get("on"),
                    }

            if len(projetos) < itens_por_pagina:
                break

            pagina += 1

            if pagina > 100:
                break

        raise ValueError(
            "Nenhum projeto da VExpenses foi encontrado "
            f"com integration_id igual a {codproj}."
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


def get_vexpenses_service() -> VExpensesService:
    """
    Cria o service reutilizando o client singleton,
    que mantém o pool de conexões HTTP.
    """

    return VExpensesService(
        client=get_vexpenses_client(),
    )