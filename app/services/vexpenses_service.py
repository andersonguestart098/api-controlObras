from __future__ import annotations

import asyncio
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import ceil
from time import monotonic
from typing import Any

from fastapi import Depends

from app.integrations.vexpenses_client import (
    VExpensesAPIError,
    VExpensesClient,
    get_vexpenses_client,
)


class VExpensesService:
    """
    Serviço de integração com a VExpenses.

    A referência de projeto aceita:

    - integration_id/CODPROJ do Sankhya;
    - ID interno do projeto na VExpenses.

    Exemplo:

        CODPROJ/integration_id: 10040000
        ID interno VExpenses:   2211713

    As despesas são consultadas diretamente em /expenses. Portanto,
    não dependem de relatório aprovado.

    O vínculo com o projeto é procurado em diferentes formatos:

    - course_id ou project_id diretamente na despesa;
    - course/project aninhado;
    - relações de rateio retornadas pelo include=apportionment;
    - relações projects, project, expense_projects ou semelhantes.
    """

    _LIMITE_API = 100
    _MAX_PAGINAS = 500

    # Cache em memória por processo/worker.
    # Evita baixar todas as páginas da VExpenses a cada atualização
    # do dashboard.
    _CACHE_DESPESAS_TTL_SEGUNDOS = 120.0
    _CACHE_PROJETOS_TTL_SEGUNDOS = 1800.0

    _cache_lock = asyncio.Lock()
    _cache_despesas: list[dict[str, Any]] | None = None
    _cache_despesas_expira_em: float = 0.0
    _cache_projetos: dict[
        int,
        tuple[float, dict[str, Any]],
    ] = {}

    def __init__(self, client: VExpensesClient) -> None:
        self.client = client

    # =========================================================
    # PROJETOS
    # =========================================================

    async def listar_projetos(
        self,
        pagina: int = 1,
        itens_por_pagina: int = 100,
    ) -> dict[str, Any]:
        self._validar_paginacao(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
        )

        response = await self.client.get(
            "/projects",
            params={
                "page": pagina,
                "limit": itens_por_pagina,
            },
        )

        projetos = self._extrair_lista(response)

        return {
            "pagina": pagina,
            "itens_por_pagina": itens_por_pagina,
            "quantidade": len(projetos),
            "data": projetos,
        }

    async def buscar_projeto_por_codproj(
        self,
        codproj: int,
    ) -> dict[str, Any] | None:
        """
        Busca um projeto pelo integration_id/CODPROJ.

        A busca é realizada localmente após paginar /projects. Isso
        evita depender do parser de search da VExpenses.
        """

        if codproj <= 0:
            raise ValueError("O CODPROJ deve ser maior que zero.")

        codproj_texto = str(codproj).strip()
        pagina = 1
        assinaturas: set[tuple[Any, ...]] = set()

        while pagina <= self._MAX_PAGINAS:
            response = await self.client.get(
                "/projects",
                params={
                    "page": pagina,
                    "limit": self._LIMITE_API,
                },
            )

            projetos = self._extrair_lista(response)

            if not projetos:
                return None

            assinatura = self._criar_assinatura_pagina(projetos)

            if assinatura in assinaturas:
                return None

            assinaturas.add(assinatura)

            for projeto in projetos:
                integration_id = projeto.get("integration_id")

                if integration_id is None:
                    continue

                if str(integration_id).strip() == codproj_texto:
                    return projeto

            if not self._tem_proxima_pagina(
                response=response,
                pagina_atual=pagina,
                quantidade_itens=len(projetos),
                limite=self._LIMITE_API,
            ):
                return None

            pagina += 1

        return None

    async def buscar_projeto_por_id(
        self,
        project_id: int,
    ) -> dict[str, Any] | None:
        if project_id <= 0:
            raise ValueError(
                "O ID do projeto deve ser maior que zero."
            )

        try:
            response = await self.client.get(
                f"/projects/{project_id}"
            )
        except VExpensesAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

        projeto = self._extrair_objeto(response)

        if projeto is None:
            return None

        id_retornado = self._to_int(projeto.get("id"))

        if (
            id_retornado is not None
            and id_retornado != project_id
        ):
            return None

        return projeto

    async def resolver_projeto(
            self,
            referencia_projeto: int,
    ) -> dict[str, Any]:
        """
        Resolve automaticamente ID interno ou CODPROJ/integration_id.

        Ordem otimizada:

        1. Tenta buscar diretamente pelo ID interno;
        2. Se não encontrar, pesquisa pelo integration_id/CODPROJ.
        """

        if referencia_projeto <= 0:
            raise ValueError(
                "A referência do projeto deve ser maior que zero."
            )

        cls = type(self)
        agora = monotonic()

        cache = cls._cache_projetos.get(
            referencia_projeto
        )

        if cache is not None:
            expira_em, projeto_cache = cache

            if agora < expira_em:
                return dict(projeto_cache)

            cls._cache_projetos.pop(
                referencia_projeto,
                None,
            )

        # Primeiro tenta como ID interno.
        projeto = await self.buscar_projeto_por_id(
            project_id=referencia_projeto,
        )

        if projeto is not None:
            self._salvar_projeto_cache(
                referencia_projeto=referencia_projeto,
                projeto=projeto,
            )

            return projeto

        # Se não existir como ID, tenta como integration_id/CODPROJ.
        projeto = await self.buscar_projeto_por_codproj(
            codproj=referencia_projeto,
        )

        if projeto is not None:
            project_id = self._to_int(
                projeto.get("id")
            )

            if project_id is None:
                raise ValueError(
                    "O projeto encontrado pelo CODPROJ não "
                    "possui ID interno válido."
                )

            self._salvar_projeto_cache(
                referencia_projeto=referencia_projeto,
                projeto=projeto,
            )

            return projeto

        raise ValueError(
            "Projeto não encontrado na VExpenses. "
            f"Referência informada: {referencia_projeto}."
        )

    @classmethod
    def _salvar_projeto_cache(
        cls,
        referencia_projeto: int,
        projeto: dict[str, Any],
    ) -> None:
        expira_em = (
            monotonic()
            + cls._CACHE_PROJETOS_TTL_SEGUNDOS
        )

        projeto_cache = dict(projeto)

        cls._cache_projetos[referencia_projeto] = (
            expira_em,
            projeto_cache,
        )

        # Também guarda pelas duas referências conhecidas.
        project_id = cls._to_int(projeto.get("id"))
        integration_id = cls._to_int(
            projeto.get("integration_id")
        )

        if project_id is not None:
            cls._cache_projetos[project_id] = (
                expira_em,
                projeto_cache,
            )

        if integration_id is not None:
            cls._cache_projetos[integration_id] = (
                expira_em,
                projeto_cache,
            )

    # =========================================================
    # DESPESAS
    # =========================================================

    async def listar_despesas(
        self,
        pagina: int = 1,
        itens_por_pagina: int = 100,
        project_id: int | None = None,
        data_inicial: date | None = None,
        data_final: date | None = None,
        somente_com_projeto: bool = True,
    ) -> dict[str, Any]:
        """
        Lista despesas diretamente pelo endpoint /expenses.

        project_id aceita tanto o CODPROJ/integration_id quanto o ID
        interno da VExpenses. A paginação de saída é aplicada depois
        dos filtros locais.
        """

        self._validar_paginacao(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
        )

        data_inicial, data_final = (
            self._aplicar_periodo_padrao(
                data_inicial=data_inicial,
                data_final=data_final,
            )
        )

        self._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        projeto: dict[str, Any] | None = None
        project_id_resolvido: int | None = None
        project_integration_id: str | None = None
        nomes_projeto: set[str] = set()

        if project_id is not None:
            projeto = await self.resolver_projeto(
                referencia_projeto=project_id,
            )

            project_id_resolvido = self._to_int(
                projeto.get("id")
            )

            if project_id_resolvido is None:
                raise ValueError(
                    "O projeto resolvido não possui ID interno válido."
                )

            project_integration_id = self._to_str(
                projeto.get("integration_id")
            )
            nomes_projeto = self._extrair_nomes_projeto(projeto)

        despesas = await self._buscar_todas_despesas()

        despesas_filtradas = self._filtrar_despesas(
            despesas=despesas,
            project_id=project_id_resolvido,
            project_integration_id=project_integration_id,
            nomes_projeto=nomes_projeto,
            data_inicial=data_inicial,
            data_final=data_final,
            somente_com_projeto=somente_com_projeto,
        )

        despesas_filtradas.sort(
            key=self._chave_ordenacao_despesa,
            reverse=True,
        )

        total_registros = len(despesas_filtradas)
        total_paginas = (
            ceil(total_registros / itens_por_pagina)
            if total_registros > 0
            else 0
        )

        indice_inicial = (pagina - 1) * itens_por_pagina
        indice_final = indice_inicial + itens_por_pagina

        movimentos = despesas_filtradas[
            indice_inicial:indice_final
        ]

        return {
            "pagina": pagina,
            "itens_por_pagina": itens_por_pagina,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "tem_proxima_pagina": pagina < total_paginas,
            "tem_pagina_anterior": pagina > 1,
            "projeto": (
                self._normalizar_projeto(projeto)
                if projeto is not None
                else None
            ),
            "filtros": {
                "referencia_recebida": project_id,
                "project_id_resolvido": project_id_resolvido,
                "project_integration_id": project_integration_id,
                "data_inicial": (
                    data_inicial.isoformat()
                    if data_inicial
                    else None
                ),
                "data_final": (
                    data_final.isoformat()
                    if data_final
                    else None
                ),
                "somente_com_projeto": somente_com_projeto,
            },
            "data": movimentos,
        }

    async def listar_despesas_por_codproj(
        self,
        codproj: int,
        pagina: int = 1,
        itens_por_pagina: int = 100,
        data_inicial: date | None = None,
        data_final: date | None = None,
    ) -> dict[str, Any]:
        return await self.listar_despesas(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
            project_id=codproj,
            data_inicial=data_inicial,
            data_final=data_final,
            somente_com_projeto=True,
        )

    async def buscar_despesa_por_id(
        self,
        expense_id: int,
    ) -> dict[str, Any] | None:
        if expense_id <= 0:
            raise ValueError(
                "O ID da despesa deve ser maior que zero."
            )

        try:
            response = await self.client.get(
                f"/expenses/{expense_id}",
                params={"include": "apportionment"},
            )
        except VExpensesAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

        despesa = self._extrair_objeto(response)

        if despesa is None:
            return None

        id_retornado = self._to_int(despesa.get("id"))

        if (
            id_retornado is not None
            and id_retornado != expense_id
        ):
            return None

        return despesa

    # =========================================================
    # RESUMO
    # =========================================================

    async def obter_resumo_despesas_por_projeto(
        self,
        project_id: int,
        data_inicial: date | None = None,
        data_final: date | None = None,
        incluir_movimentos: bool = False,
    ) -> dict[str, Any]:
        """
        Gera o resumo diretamente pelas despesas vinculadas ao projeto.

        O valor atribuído ao projeto respeita o percentual do rateio
        quando esse percentual estiver presente. Na ausência dele, o
        valor integral da despesa é considerado.
        """

        data_inicial, data_final = (
            self._aplicar_periodo_padrao(
                data_inicial=data_inicial,
                data_final=data_final,
            )
        )

        self._validar_periodo(
            data_inicial=data_inicial,
            data_final=data_final,
        )

        projeto = await self.resolver_projeto(
            referencia_projeto=project_id,
        )

        project_id_resolvido = self._to_int(projeto.get("id"))

        if project_id_resolvido is None:
            raise ValueError(
                "O projeto resolvido não possui ID interno válido."
            )

        project_integration_id = self._to_str(
            projeto.get("integration_id")
        )
        nomes_projeto = self._extrair_nomes_projeto(projeto)

        todas_despesas = await self._buscar_todas_despesas()

        despesas = self._filtrar_despesas(
            despesas=todas_despesas,
            project_id=project_id_resolvido,
            project_integration_id=project_integration_id,
            nomes_projeto=nomes_projeto,
            data_inicial=data_inicial,
            data_final=data_final,
            somente_com_projeto=True,
        )

        despesas.sort(
            key=self._chave_ordenacao_despesa,
            reverse=True,
        )

        total = Decimal("0")
        total_reembolsavel = Decimal("0")
        total_nao_reembolsavel = Decimal("0")
        quantidade_reembolsavel = 0
        quantidade_nao_reembolsavel = 0

        por_tipo: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "expense_type_id": None,
                "descricao": None,
                "quantidade": 0,
                "valor": Decimal("0"),
            }
        )
        por_usuario: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "user_id": None,
                "nome": None,
                "quantidade": 0,
                "valor": Decimal("0"),
            }
        )
        por_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "data": None,
                "quantidade": 0,
                "valor": Decimal("0"),
            }
        )

        for despesa in despesas:
            valor = self._obter_valor_considerado(despesa)
            total += valor

            reembolsavel = self._to_bool(
                despesa.get("reimbursable")
            )

            if reembolsavel:
                quantidade_reembolsavel += 1
                total_reembolsavel += valor
            else:
                quantidade_nao_reembolsavel += 1
                total_nao_reembolsavel += valor

            self._acumular_por_tipo(
                acumulador=por_tipo,
                despesa=despesa,
                valor=valor,
            )
            self._acumular_por_usuario(
                acumulador=por_usuario,
                despesa=despesa,
                valor=valor,
            )
            self._acumular_por_data(
                acumulador=por_data,
                despesa=despesa,
                valor=valor,
            )

        resposta: dict[str, Any] = {
            "referencia_recebida": project_id,
            "project_id_resolvido": project_id_resolvido,
            "projeto": self._normalizar_projeto(projeto),
            "periodo": {
                "data_inicial": (
                    data_inicial.isoformat()
                    if data_inicial
                    else None
                ),
                "data_final": (
                    data_final.isoformat()
                    if data_final
                    else None
                ),
            },
            "quantidade_despesas": len(despesas),
            "total_despesas": self._decimal_para_float(total),
            "reembolsaveis": {
                "quantidade": quantidade_reembolsavel,
                "valor": self._decimal_para_float(
                    total_reembolsavel
                ),
            },
            "nao_reembolsaveis": {
                "quantidade": quantidade_nao_reembolsavel,
                "valor": self._decimal_para_float(
                    total_nao_reembolsavel
                ),
            },
            "por_tipo_despesa": self._finalizar_agrupamento(
                acumulador=por_tipo,
                campo_ordenacao="valor",
                reverso=True,
            ),
            "por_usuario": self._finalizar_agrupamento(
                acumulador=por_usuario,
                campo_ordenacao="valor",
                reverso=True,
            ),
            "por_data": self._finalizar_agrupamento(
                acumulador=por_data,
                campo_ordenacao="data",
                reverso=False,
            ),
        }

        if incluir_movimentos:
            resposta["movimentos"] = despesas

        return resposta

    async def obter_resumo_dashboard(
        self,
        project_id: int,
        data_inicial: date | None = None,
        data_final: date | None = None,
        incluir_movimentos: bool = False,
    ) -> dict[str, Any]:
        """Alias para manter compatibilidade com o router antigo."""

        return await self.obter_resumo_despesas_por_projeto(
            project_id=project_id,
            data_inicial=data_inicial,
            data_final=data_final,
            incluir_movimentos=incluir_movimentos,
        )

    # =========================================================
    # CONSULTAS INTERNAS
    # =========================================================

    async def _buscar_todas_despesas(
        self,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Busca todas as despesas ativas diretamente em /expenses.

        O resultado completo fica em cache por 2 minutos. Assim, a
        primeira chamada pode continuar dependendo da paginação da
        VExpenses, mas as próximas chamadas do dashboard reutilizam
        os mesmos dados.
        """

        cls = type(self)
        agora = monotonic()

        if (
            not force_refresh
            and cls._cache_despesas is not None
            and agora < cls._cache_despesas_expira_em
        ):
            return cls._cache_despesas

        async with cls._cache_lock:
            # Outra requisição pode ter atualizado o cache enquanto
            # esta aguardava o lock.
            agora = monotonic()

            if (
                not force_refresh
                and cls._cache_despesas is not None
                and agora < cls._cache_despesas_expira_em
            ):
                return cls._cache_despesas

            pagina = 1
            despesas: list[dict[str, Any]] = []
            ids_encontrados: set[str] = set()
            assinaturas: set[tuple[Any, ...]] = set()

            while pagina <= self._MAX_PAGINAS:
                response = await self.client.get(
                    "/expenses",
                    params={
                        "page": pagina,
                        "limit": self._LIMITE_API,
                        "include": "apportionment",
                        "search": "on:1",
                        "searchFields": "on:=",
                        "searchJoin": "and",
                    },
                )

                itens = self._extrair_lista(response)

                if not itens:
                    break

                assinatura = self._criar_assinatura_pagina(
                    itens
                )

                if assinatura in assinaturas:
                    break

                assinaturas.add(assinatura)
                quantidade_novos = 0

                for despesa in itens:
                    chave = self._chave_unica_despesa(
                        despesa
                    )

                    if chave in ids_encontrados:
                        continue

                    ids_encontrados.add(chave)
                    despesas.append(despesa)
                    quantidade_novos += 1

                if quantidade_novos == 0:
                    break

                if not self._tem_proxima_pagina(
                    response=response,
                    pagina_atual=pagina,
                    quantidade_itens=len(itens),
                    limite=self._LIMITE_API,
                ):
                    break

                pagina += 1

            cls._cache_despesas = despesas
            cls._cache_despesas_expira_em = (
                monotonic()
                + cls._CACHE_DESPESAS_TTL_SEGUNDOS
            )

            return despesas

    @classmethod
    def limpar_cache(cls) -> None:
        """Limpa manualmente os caches locais do service."""

        cls._cache_despesas = None
        cls._cache_despesas_expira_em = 0.0
        cls._cache_projetos.clear()

    # =========================================================
    # FILTROS E VÍNCULO DE PROJETO
    # =========================================================

    def _filtrar_despesas(
        self,
        despesas: list[dict[str, Any]],
        project_id: int | None,
        project_integration_id: str | None,
        nomes_projeto: set[str],
        data_inicial: date | None,
        data_final: date | None,
        somente_com_projeto: bool,
    ) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []

        for despesa in despesas:
            vinculo: dict[str, Any] | None = None

            if project_id is not None:
                vinculo = self._localizar_vinculo_projeto(
                    despesa=despesa,
                    project_id=project_id,
                    project_integration_id=(
                        project_integration_id
                    ),
                    nomes_projeto=nomes_projeto,
                )

                if vinculo is None:
                    continue

            elif somente_com_projeto:
                if not self._despesa_possui_algum_projeto(
                    despesa
                ):
                    continue

            data_despesa = self._parse_date(
                despesa.get("date")
            )

            if (
                data_inicial is not None
                and (
                    data_despesa is None
                    or data_despesa < data_inicial
                )
            ):
                continue

            if (
                data_final is not None
                and (
                    data_despesa is None
                    or data_despesa > data_final
                )
            ):
                continue

            despesa_normalizada = dict(despesa)

            if vinculo is not None:
                percentual = self._to_decimal_ou_none(
                    vinculo.get("percentage")
                    or vinculo.get("percentual")
                )

                despesa_normalizada["project_allocation"] = {
                    "project_id": project_id,
                    "integration_id": project_integration_id,
                    "percentage": (
                        self._decimal_para_float(percentual)
                        if percentual is not None
                        else None
                    ),
                    "source": vinculo.get("__source_relation"),
                }

            resultado.append(despesa_normalizada)

        return resultado

    @classmethod
    def _despesa_possui_algum_projeto(
        cls,
        despesa: dict[str, Any],
    ) -> bool:
        if cls._to_int(despesa.get("course_id")) is not None:
            return True

        if cls._to_int(despesa.get("project_id")) is not None:
            return True

        for nome_relacao, relacao in (
            ("course", despesa.get("course")),
            ("project", despesa.get("project")),
        ):
            objeto = cls._extrair_objeto_relacao(relacao)

            if objeto and cls._objeto_tem_dados_de_projeto(
                objeto,
                nome_relacao=nome_relacao,
            ):
                return True

        for vinculo in cls._extrair_vinculos_projeto(despesa):
            origem = str(
                vinculo.get("__source_relation") or ""
            )

            if cls._objeto_tem_dados_de_projeto(
                vinculo,
                nome_relacao=origem,
            ):
                return True

        return False

    @classmethod
    def _localizar_vinculo_projeto(
        cls,
        despesa: dict[str, Any],
        project_id: int,
        project_integration_id: str | None,
        nomes_projeto: set[str],
    ) -> dict[str, Any] | None:
        course_id = cls._to_int(despesa.get("course_id"))

        if course_id == project_id:
            return {
                "course_id": course_id,
                "percentage": 100,
                "__source_relation": "course_id",
            }

        direct_project_id = cls._to_int(
            despesa.get("project_id")
        )

        if direct_project_id == project_id:
            return {
                "project_id": direct_project_id,
                "percentage": 100,
                "__source_relation": "project_id",
            }

        for nome_relacao, relacao in (
            ("course", despesa.get("course")),
            ("project", despesa.get("project")),
        ):
            objeto = cls._extrair_objeto_relacao(relacao)

            if objeto is None:
                continue

            candidato = dict(objeto)
            candidato["__source_relation"] = nome_relacao

            if cls._vinculo_corresponde_ao_projeto(
                vinculo=candidato,
                project_id=project_id,
                project_integration_id=(
                    project_integration_id
                ),
                nomes_projeto=nomes_projeto,
            ):
                candidato.setdefault("percentage", 100)
                return candidato

        for vinculo in cls._extrair_vinculos_projeto(despesa):
            if cls._vinculo_corresponde_ao_projeto(
                vinculo=vinculo,
                project_id=project_id,
                project_integration_id=(
                    project_integration_id
                ),
                nomes_projeto=nomes_projeto,
            ):
                return vinculo

        return None

    @classmethod
    def _vinculo_corresponde_ao_projeto(
        cls,
        vinculo: dict[str, Any],
        project_id: int,
        project_integration_id: str | None,
        nomes_projeto: set[str],
    ) -> bool:
        origem = str(
            vinculo.get("__source_relation") or ""
        ).lower()

        ids_diretos = (
            vinculo.get("project_id"),
            vinculo.get("course_id"),
            vinculo.get("expense_project_id"),
        )

        if any(
            cls._to_int(valor) == project_id
            for valor in ids_diretos
        ):
            return True

        # Em relações explicitamente chamadas project/course, o campo
        # id normalmente é o ID do próprio projeto. Em apportionment,
        # id costuma ser o ID do rateio; por isso não é comparado.
        if origem not in {"apportionment", "apportionments"}:
            if cls._to_int(vinculo.get("id")) == project_id:
                return True

        integration_id_esperado = cls._to_str(
            project_integration_id
        )

        integration_ids = (
            vinculo.get("project_integration_id"),
            vinculo.get("course_integration_id"),
            vinculo.get("integration_id"),
        )

        if integration_id_esperado is not None:
            if any(
                cls._to_str(valor) == integration_id_esperado
                for valor in integration_ids
            ):
                return True

        for chave in ("project", "course"):
            aninhado = cls._extrair_objeto_relacao(
                vinculo.get(chave)
            )

            if aninhado is None:
                continue

            if cls._to_int(aninhado.get("id")) == project_id:
                return True

            if (
                integration_id_esperado is not None
                and cls._to_str(
                    aninhado.get("integration_id")
                )
                == integration_id_esperado
            ):
                return True

            if cls._objeto_corresponde_por_nome(
                aninhado,
                nomes_projeto,
            ):
                return True

        if cls._objeto_corresponde_por_nome(
            vinculo,
            nomes_projeto,
        ):
            return True

        return False

    @classmethod
    def _extrair_vinculos_projeto(
        cls,
        despesa: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Normaliza as possíveis relações de projeto/rateio."""

        nomes_relacao = (
            "apportionment",
            "apportionments",
            "projects",
            "project",
            "courses",
            "course",
            "expense_projects",
            "expense_project",
            "expenseProjects",
            "expenseProject",
        )

        resultado: list[dict[str, Any]] = []

        for nome in nomes_relacao:
            relacao = despesa.get(nome)

            for item in cls._normalizar_relacao_para_lista(relacao):
                registro = dict(item)
                registro["__source_relation"] = nome
                resultado.append(registro)

        return resultado

    @classmethod
    def _normalizar_relacao_para_lista(
        cls,
        relacao: Any,
    ) -> list[dict[str, Any]]:
        if relacao is None:
            return []

        if isinstance(relacao, list):
            return [
                item
                for item in relacao
                if isinstance(item, dict)
            ]

        if not isinstance(relacao, dict):
            return []

        data = relacao.get("data")

        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        if isinstance(data, dict):
            return [data]

        items = relacao.get("items")

        if isinstance(items, list):
            return [
                item
                for item in items
                if isinstance(item, dict)
            ]

        return [relacao]

    @classmethod
    def _extrair_objeto_relacao(
        cls,
        relacao: Any,
    ) -> dict[str, Any] | None:
        itens = cls._normalizar_relacao_para_lista(relacao)
        return itens[0] if itens else None

    @classmethod
    def _objeto_tem_dados_de_projeto(
        cls,
        objeto: dict[str, Any],
        nome_relacao: str,
    ) -> bool:
        campos_explicitos = (
            "project_id",
            "course_id",
            "expense_project_id",
            "project_integration_id",
            "course_integration_id",
            "project",
            "course",
            "project_name",
            "course_name",
        )

        if any(
            objeto.get(campo) not in (None, "", [], {})
            for campo in campos_explicitos
        ):
            return True

        origem = nome_relacao.lower()

        if origem in {
            "project",
            "projects",
            "course",
            "courses",
            "expense_project",
            "expense_projects",
            "expenseproject",
            "expenseprojects",
        }:
            return objeto.get("id") is not None

        # Em apportionment, não consideramos um simples id como projeto,
        # pois ele pode ser apenas o identificador do próprio rateio.
        # Uma descrição sem reimbursable_company_id é tratada como possível
        # rateio de projeto.
        if origem in {"apportionment", "apportionments"}:
            return (
                objeto.get("reimbursable_company_id") is None
                and bool(
                    cls._to_str(
                        objeto.get("description")
                        or objeto.get("name")
                    )
                )
            )

        return False

    @classmethod
    def _objeto_corresponde_por_nome(
        cls,
        objeto: dict[str, Any],
        nomes_projeto: set[str],
    ) -> bool:
        if not nomes_projeto:
            return False

        candidatos = (
            objeto.get("name"),
            objeto.get("project_name"),
            objeto.get("course_name"),
            objeto.get("description"),
            objeto.get("company_name"),
        )

        for candidato in candidatos:
            texto = cls._normalizar_texto(candidato)

            if texto and texto in nomes_projeto:
                return True

        return False

    @classmethod
    def _extrair_nomes_projeto(
        cls,
        projeto: dict[str, Any],
    ) -> set[str]:
        nomes: set[str] = set()

        for valor in (
            projeto.get("name"),
            projeto.get("company_name"),
            projeto.get("description"),
        ):
            texto = cls._normalizar_texto(valor)

            if texto:
                nomes.add(texto)

        return nomes

    # =========================================================
    # AGRUPAMENTOS
    # =========================================================

    def _acumular_por_tipo(
        self,
        acumulador: dict[str, dict[str, Any]],
        despesa: dict[str, Any],
        valor: Decimal,
    ) -> None:
        expense_type_id = self._to_int(
            despesa.get("expense_type_id")
        )
        expense_type = self._extrair_relacao(
            despesa.get("expense_type")
        )

        descricao = (
            expense_type.get("name")
            or expense_type.get("description")
            or despesa.get("expense_type_name")
            or (
                f"Tipo {expense_type_id}"
                if expense_type_id is not None
                else "Sem tipo"
            )
        )

        chave = (
            str(expense_type_id)
            if expense_type_id is not None
            else "sem_tipo"
        )

        item = acumulador[chave]
        item["expense_type_id"] = expense_type_id
        item["descricao"] = descricao
        item["quantidade"] += 1
        item["valor"] += valor

    def _acumular_por_usuario(
        self,
        acumulador: dict[str, dict[str, Any]],
        despesa: dict[str, Any],
        valor: Decimal,
    ) -> None:
        user_id = self._to_int(despesa.get("user_id"))
        user = self._extrair_relacao(despesa.get("user"))

        nome = (
            user.get("name")
            or user.get("full_name")
            or despesa.get("user_name")
            or (
                f"Usuário {user_id}"
                if user_id is not None
                else "Sem usuário"
            )
        )

        chave = (
            str(user_id)
            if user_id is not None
            else "sem_usuario"
        )

        item = acumulador[chave]
        item["user_id"] = user_id
        item["nome"] = nome
        item["quantidade"] += 1
        item["valor"] += valor

    def _acumular_por_data(
        self,
        acumulador: dict[str, dict[str, Any]],
        despesa: dict[str, Any],
        valor: Decimal,
    ) -> None:
        data_despesa = self._parse_date(despesa.get("date"))
        chave = (
            data_despesa.isoformat()
            if data_despesa is not None
            else "sem_data"
        )

        item = acumulador[chave]
        item["data"] = (
            data_despesa.isoformat()
            if data_despesa is not None
            else None
        )
        item["quantidade"] += 1
        item["valor"] += valor

    def _finalizar_agrupamento(
        self,
        acumulador: dict[str, dict[str, Any]],
        campo_ordenacao: str,
        reverso: bool,
    ) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []

        for item in acumulador.values():
            registro = dict(item)
            valor = registro.get("valor")

            if isinstance(valor, Decimal):
                registro["valor"] = self._decimal_para_float(valor)

            resultado.append(registro)

        return sorted(
            resultado,
            key=lambda registro: (
                registro.get(campo_ordenacao)
                if registro.get(campo_ordenacao) is not None
                else ""
            ),
            reverse=reverso,
        )

    # =========================================================
    # NORMALIZAÇÃO DE RESPOSTA
    # =========================================================

    @staticmethod
    def _normalizar_projeto(
        projeto: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": projeto.get("id"),
            "integration_id": projeto.get("integration_id"),
            "name": projeto.get("name"),
            "company_name": projeto.get("company_name"),
            "on": projeto.get("on"),
        }

    @classmethod
    def _extrair_lista(
        cls,
        response: Any,
    ) -> list[dict[str, Any]]:
        if isinstance(response, list):
            return [
                item
                for item in response
                if isinstance(item, dict)
            ]

        if not isinstance(response, dict):
            return []

        data = response.get("data")

        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        if isinstance(data, dict):
            for chave in (
                "data",
                "items",
                "results",
                "records",
            ):
                itens = data.get(chave)

                if isinstance(itens, list):
                    return [
                        item
                        for item in itens
                        if isinstance(item, dict)
                    ]

        for chave in ("items", "results", "records"):
            itens = response.get(chave)

            if isinstance(itens, list):
                return [
                    item
                    for item in itens
                    if isinstance(item, dict)
                ]

        return []

    @classmethod
    def _extrair_objeto(
        cls,
        response: Any,
    ) -> dict[str, Any] | None:
        if not isinstance(response, dict):
            return None

        data = response.get("data")

        if isinstance(data, dict):
            nested_data = data.get("data")

            if isinstance(nested_data, dict):
                return nested_data

            return data

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
            return None

        if "id" in response:
            return response

        return None

    @staticmethod
    def _extrair_relacao(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}

        nested_data = value.get("data")

        if isinstance(nested_data, dict):
            return nested_data

        return value

    # =========================================================
    # PAGINAÇÃO
    # =========================================================

    @classmethod
    def _tem_proxima_pagina(
        cls,
        response: Any,
        pagina_atual: int,
        quantidade_itens: int,
        limite: int,
    ) -> bool:
        if not isinstance(response, dict):
            return quantidade_itens >= limite

        containers: list[dict[str, Any]] = [response]
        data = response.get("data")

        if isinstance(data, dict):
            containers.append(data)

        indice = 0

        while indice < len(containers):
            container = containers[indice]
            indice += 1

            meta = container.get("meta")
            if isinstance(meta, dict):
                containers.append(meta)

            pagination = container.get("pagination")
            if isinstance(pagination, dict):
                containers.append(pagination)

            current_page = cls._to_int(
                container.get("current_page")
                or container.get("currentPage")
                or container.get("page")
            )
            last_page = cls._to_int(
                container.get("last_page")
                or container.get("lastPage")
                or container.get("total_pages")
                or container.get("totalPages")
            )

            if (
                current_page is not None
                and last_page is not None
            ):
                return current_page < last_page

            next_page = container.get("next_page")
            if next_page is not None:
                return bool(next_page)

            next_page_url = container.get("next_page_url")
            if next_page_url is not None:
                return bool(next_page_url)

        links = response.get("links")

        if isinstance(links, dict):
            next_link = links.get("next")
            if next_link is not None:
                return bool(next_link)

        return quantidade_itens >= limite

    @staticmethod
    def _criar_assinatura_pagina(
        itens: list[dict[str, Any]],
    ) -> tuple[Any, ...]:
        ids = [
            item.get("id")
            for item in itens
            if item.get("id") is not None
        ]

        return (
            len(itens),
            ids[0] if ids else None,
            ids[-1] if ids else None,
        )

    @staticmethod
    def _chave_unica_despesa(
        despesa: dict[str, Any],
    ) -> str:
        expense_id = despesa.get("id")

        if expense_id is not None:
            return f"id:{expense_id}"

        return (
            f"user:{despesa.get('user_id')}:"
            f"date:{despesa.get('date')}:"
            f"value:{despesa.get('value')}:"
            f"title:{despesa.get('title')}"
        )

    # =========================================================
    # VALORES E CONVERSÕES
    # =========================================================

    @classmethod
    def _obter_valor_despesa(
        cls,
        despesa: dict[str, Any],
    ) -> Decimal:
        converted_value = despesa.get("converted_value")

        if converted_value not in {None, ""}:
            return cls._to_decimal(converted_value)

        return cls._to_decimal(despesa.get("value"))

    @classmethod
    def _obter_valor_considerado(
        cls,
        despesa: dict[str, Any],
    ) -> Decimal:
        valor = cls._obter_valor_despesa(despesa)
        allocation = despesa.get("project_allocation")

        if not isinstance(allocation, dict):
            return valor

        percentual = cls._to_decimal_ou_none(
            allocation.get("percentage")
        )

        if percentual is None:
            return valor

        if percentual < 0:
            return Decimal("0")

        fator = (
            percentual / Decimal("100")
            if percentual > 1
            else percentual
        )

        return valor * fator

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        resultado = VExpensesService._to_decimal_ou_none(value)
        return resultado if resultado is not None else Decimal("0")

    @staticmethod
    def _to_decimal_ou_none(value: Any) -> Decimal | None:
        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        if isinstance(value, bool):
            return Decimal(int(value))

        if isinstance(value, int):
            return Decimal(value)

        if isinstance(value, float):
            return Decimal(str(value))

        texto = str(value).strip()

        if not texto:
            return None

        texto = texto.replace("R$", "").strip()
        texto = texto.replace("%", "").strip()
        texto = texto.replace(" ", "")

        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "")
                texto = texto.replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")

        try:
            return Decimal(texto)
        except InvalidOperation:
            return None

    @staticmethod
    def _decimal_para_float(value: Decimal) -> float:
        return float(value.quantize(Decimal("0.01")))

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None

        if isinstance(value, bool):
            return int(value)

        try:
            texto = str(value).strip()
            if not texto:
                return None
            return int(float(texto))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_str(value: Any) -> str | None:
        if value is None:
            return None

        texto = str(value).strip()
        return texto or None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        if isinstance(value, int):
            return value == 1

        return str(value).strip().lower() in {
            "1",
            "true",
            "t",
            "yes",
            "y",
            "sim",
            "s",
        }

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        texto = str(value).strip()

        if not texto:
            return None

        formatos = (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%d/%m/%Y",
        )

        for formato in formatos:
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(
                texto.replace("Z", "+00:00")
            ).date()
        except ValueError:
            return None

    @staticmethod
    def _normalizar_texto(value: Any) -> str:
        if value is None:
            return ""

        texto = str(value).strip().casefold()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caractere
            for caractere in texto
            if not unicodedata.combining(caractere)
        )
        return " ".join(texto.split())

    @classmethod
    def _chave_ordenacao_despesa(
        cls,
        despesa: dict[str, Any],
    ) -> tuple[date, int]:
        data_despesa = (
            cls._parse_date(despesa.get("date"))
            or date.min
        )
        expense_id = cls._to_int(despesa.get("id")) or 0
        return data_despesa, expense_id

    @staticmethod
    def _aplicar_periodo_padrao(
        data_inicial: date | None,
        data_final: date | None,
    ) -> tuple[date, date]:
        """
        Usa o ano corrente quando nenhuma data é informada.

        Em 2026, por exemplo, o padrão será:

            data_inicial = 2026-01-01
            data_final = data de hoje
        """

        hoje = date.today()

        if data_inicial is None and data_final is None:
            return date(hoje.year, 1, 1), hoje

        if data_inicial is None:
            assert data_final is not None
            return date(data_final.year, 1, 1), data_final

        if data_final is None:
            return data_inicial, hoje

        return data_inicial, data_final

    # =========================================================
    # VALIDAÇÕES
    # =========================================================

    @staticmethod
    def _validar_paginacao(
        pagina: int,
        itens_por_pagina: int,
    ) -> None:
        if pagina < 1:
            raise ValueError(
                "A página deve ser maior ou igual a 1."
            )

        if not 1 <= itens_por_pagina <= 100:
            raise ValueError(
                "A quantidade de itens por página deve estar "
                "entre 1 e 100."
            )

    @staticmethod
    def _validar_periodo(
        data_inicial: date | None,
        data_final: date | None,
    ) -> None:
        if (
            data_inicial is not None
            and data_final is not None
            and data_inicial > data_final
        ):
            raise ValueError(
                "A data inicial não pode ser posterior à data final."
            )


def get_vexpenses_service(
    client: VExpensesClient = Depends(get_vexpenses_client),
) -> VExpensesService:
    return VExpensesService(client=client)