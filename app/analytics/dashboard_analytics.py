from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from typing import Any

from app.analytics.devolucoes_interno_obras import (
    DevolucoesInternoObrasAnalytics,
)
from app.analytics.impostos import ImpostosAnalytics
from app.analytics.interno_obras import (
    InternoObrasAnalytics,
)
from app.analytics.remessas import RemessasAnalytics
from app.analytics.remessas_transporte import (
    RemessasTransporteAnalytics,
)
from app.analytics.vendas import VendasAnalytics


class DashboardAnalytics:
    ZERO = Decimal("0")
    CENTAVOS = Decimal("0.01")

    @classmethod
    def build_kpis(
            cls,
            *,
            notas: list[dict[str, Any]],
            itens_notas: list[dict[str, Any]],
            interno_obras: list[dict[str, Any]],
            devolucoes_interno_obras: list[
                dict[str, Any]
            ],
            remessas: list[dict[str, Any]],
            remessas_transporte: list[dict[str, Any]],
            notas_impostos: list[dict[str, Any]],
            compras: list[dict[str, Any]],
            bonificados: list[dict[str, Any]],
            mao_de_obra: list[dict[str, Any]],
            pagamentos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Monta todos os indicadores do dashboard.

        As devoluções de Interno Obras ficam
        separadas das devoluções de vendas normais
        e abatem exclusivamente o Interno Obras.

        Remessas:

        - Remessa futura   -> RemessasAnalytics
        - Remessa transporte
          -> RemessasTransporteAnalytics

        As duas trabalham apenas com cabeçalho.
        """

        devolucoes_interno_obras_kpis = (
            DevolucoesInternoObrasAnalytics.build_kpis(
                devolucoes_interno_obras
            )
        )

        interno_obras_kpis = (
            InternoObrasAnalytics.build_kpis(
                interno_obras=interno_obras,
                devolucoes_interno_obras=(
                    devolucoes_interno_obras
                ),
            )
        )

        impostos_kpis = (
            ImpostosAnalytics.build_kpis(
                notas_impostos
            )
        )

        impostos_kpis = (
            cls._aplicar_devolucoes_interno_obras(
                impostos=impostos_kpis,
                devolucoes=(
                    devolucoes_interno_obras_kpis
                ),
            )
        )

        return {
            "vendas": (
                VendasAnalytics.build_kpis(
                    notas=notas,
                    itens_notas=itens_notas,
                )
            ),

            "interno_obras": interno_obras_kpis,

            "devolucoes_interno_obras": (
                devolucoes_interno_obras_kpis
            ),

            "remessa_futura": (
                RemessasAnalytics.build_kpis(
                    remessas=remessas,
                    remessas_transporte=(
                        remessas_transporte
                    ),
                )
            ),

            "remessa_transporte": (
                RemessasTransporteAnalytics.build_kpis(
                    remessas_transporte
                )
            ),

            "impostos": impostos_kpis,

            "compras": (
                cls._build_movimento_kpis(
                    rows=compras,
                    incluir_custo=True,
                )
            ),

            "bonificados": (
                cls._build_movimento_kpis(
                    rows=bonificados,
                    incluir_custo=True,
                )
            ),

            "mao_de_obra": (
                cls._build_movimento_kpis(
                    rows=mao_de_obra,
                    incluir_custo=False,
                )
            ),

            "pagamentos": (
                cls._build_pagamentos_kpis(
                    pagamentos
                )
            ),

        }

    @classmethod
    def _aplicar_devolucoes_interno_obras(
        cls,
        *,
        impostos: dict[str, Any],
        devolucoes: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Adiciona as devoluções do Interno Obras
        como categoria separada nos impostos.

        Também subtrai seus valores somente de:

        - Interno Obras
        - Consolidado líquido

        A categoria Devoluções gerais permanece
        sem alteração.
        """

        impostos_ajustados: dict[str, Any] = {}

        for key, value in impostos.items():
            if isinstance(value, dict):
                impostos_ajustados[key] = dict(value)
            else:
                impostos_ajustados[key] = value

        grupo_devolucoes = {
            "icms": cls._money(
                cls._to_decimal(
                    devolucoes.get("icms")
                )
            ),

            "pis": cls._money(
                cls._to_decimal(
                    devolucoes.get("pis")
                )
            ),

            "cofins": cls._money(
                cls._to_decimal(
                    devolucoes.get("cofins")
                )
            ),

            "federais": cls._money(
                cls._to_decimal(
                    devolucoes.get("federais")
                )
            ),

            "total_tributos": cls._money(
                cls._to_decimal(
                    devolucoes.get(
                        "total_tributos"
                    )
                )
            ),

            "comissao": cls._money(
                cls._to_decimal(
                    devolucoes.get("comissao")
                )
            ),
        }

        # A categoria é mantida positiva no backend.
        # O frontend poderá mostrar com sinal negativo.
        impostos_ajustados[
            "devolucoes_interno_obras"
        ] = grupo_devolucoes

        impostos_ajustados["interno_obras"] = (
            cls._subtrair_grupo_impostos(
                base=impostos_ajustados.get(
                    "interno_obras",
                    {},
                ),
                subtrair=grupo_devolucoes,
            )
        )

        impostos_ajustados[
            "consolidado_liquido"
        ] = cls._subtrair_grupo_impostos(
            base=impostos_ajustados.get(
                "consolidado_liquido",
                {},
            ),
            subtrair=grupo_devolucoes,
        )

        return impostos_ajustados

    @classmethod
    def _subtrair_grupo_impostos(
        cls,
        *,
        base: dict[str, Any],
        subtrair: dict[str, Any],
    ) -> dict[str, float]:
        """
        Subtrai ICMS, PIS, COFINS, tributos
        federais, tributos totais e comissão.
        """

        campos = (
            "icms",
            "pis",
            "cofins",
            "federais",
            "total_tributos",
            "comissao",
        )

        resultado: dict[str, float] = {}

        for campo in campos:
            valor_base = cls._to_decimal(
                base.get(campo)
            )

            valor_subtrair = cls._to_decimal(
                subtrair.get(campo)
            )

            resultado[campo] = cls._money(
                valor_base - valor_subtrair
            )

        return resultado

    @classmethod
    def _build_pagamentos_kpis(
            cls,
            rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Monta os indicadores financeiros dos títulos
        vinculados à obra.

        Separa corretamente:

        - dinheiro efetivamente recebido em conta;
        - títulos quitados por compensação;
        - títulos em aberto;
        - títulos vencidos;
        - outras formas de baixa.
        """

        # Evita somar o mesmo título mais de uma vez
        # caso algum JOIN duplique o NUFIN.
        titulos_por_nufin: dict[Any, dict[str, Any]] = {}
        titulos_sem_nufin: list[dict[str, Any]] = []

        for row in rows:
            nufin = row.get("nufin")

            if nufin is None:
                titulos_sem_nufin.append(row)
                continue

            titulos_por_nufin[nufin] = row

        titulos = (
                list(titulos_por_nufin.values())
                + titulos_sem_nufin
        )

        recebidos_em_conta: list[dict[str, Any]] = []
        compensados: list[dict[str, Any]] = []
        vencidos: list[dict[str, Any]] = []
        em_aberto: list[dict[str, Any]] = []
        outras_baixas: list[dict[str, Any]] = []

        for row in titulos:
            forma_liquidacao = str(
                row.get("forma_liquidacao") or ""
            ).strip().upper()

            if forma_liquidacao == "RECEBIDO EM CONTA":
                recebidos_em_conta.append(row)

            elif forma_liquidacao in (
                    "QUITADO POR COMPENSACAO FINANCEIRA",
                    "QUITADO COM CREDITO DE DEVOLUCAO",
            ):
                compensados.append(row)

            elif forma_liquidacao == "VENCIDO":
                vencidos.append(row)

            elif forma_liquidacao in (
                    "EM ABERTO",
                    "EM_ABERTO",
                    "ABERTO",
            ):
                em_aberto.append(row)

            elif forma_liquidacao == "OUTRA FORMA DE BAIXA":
                outras_baixas.append(row)

        valor_titulos = cls._sum_field(
            titulos,
            "valor_titulo",
        )

        valor_liquido = cls._sum_field(
            titulos,
            "valor_liquido",
        )

        # Dinheiro que realmente entrou no banco.
        valor_recebido_em_conta = cls._sum_field(
            titulos,
            "valor_recebido_em_conta",
        )

        # Títulos quitados com créditos/compensações.
        valor_compensado = cls._sum_field(
            titulos,
            "valor_compensado",
        )

        # Inclui títulos normais em aberto e vencidos.
        saldo_aberto = cls._sum_field(
            titulos,
            "valor_em_aberto",
        )

        # Apenas títulos vencidos.
        valor_vencido = cls._sum_field(
            titulos,
            "valor_vencido",
        )

        # Apenas títulos ainda não vencidos.
        valor_em_aberto = cls._sum_field(
            em_aberto,
            "valor_em_aberto",
        )

        valor_outras_baixas = cls._sum_field(
            outras_baixas,
            "valor_baixa",
        )

        quantidade_recebidos = len(recebidos_em_conta)
        quantidade_compensados = len(compensados)
        quantidade_outras_baixas = len(outras_baixas)

        quantidade_quitados = (
                quantidade_recebidos
                + quantidade_compensados
                + quantidade_outras_baixas
        )

        valor_quitado_total = (
                valor_recebido_em_conta
                + valor_compensado
                + valor_outras_baixas
        )

        return {
            "quantidade_titulos": len(titulos),

            # Recebimento bancário real
            "quantidade_recebidos_em_conta": (
                quantidade_recebidos
            ),
            "valor_recebido_em_conta": cls._money(
                valor_recebido_em_conta
            ),

            # Compensações sem entrada de dinheiro
            "quantidade_compensados": (
                quantidade_compensados
            ),
            "valor_compensado": cls._money(
                valor_compensado
            ),

            # Outras baixas
            "quantidade_outras_baixas": (
                quantidade_outras_baixas
            ),
            "valor_outras_baixas": cls._money(
                valor_outras_baixas
            ),

            # Total de títulos liquidados,
            # independentemente da forma de liquidação
            "quantidade_quitados": quantidade_quitados,
            "valor_quitado_total": cls._money(
                valor_quitado_total
            ),

            "quantidade_vencidos": len(vencidos),
            "quantidade_em_aberto": len(em_aberto),

            "valor_titulos": cls._money(
                valor_titulos
            ),

            "valor_liquido": cls._money(
                valor_liquido
            ),

            "saldo_aberto": cls._money(
                saldo_aberto
            ),

            "valor_vencido": cls._money(
                valor_vencido
            ),

            "valor_em_aberto": cls._money(
                valor_em_aberto
            ),

        "quantidade_pagos": quantidade_recebidos,

        "valor_pago": cls._money(
            valor_recebido_em_conta
        ),
        }
    @classmethod
    def _build_movimento_kpis(
        cls,
        *,
        rows: list[dict[str, Any]],
        incluir_custo: bool,
    ) -> dict[str, Any]:
        nunotas = {
            row.get("nunota")
            for row in rows
            if row.get("nunota") is not None
        }

        valor_nota = cls._sum_field(
            rows,
            "vlrnota",
        )

        valor_icms = cls._sum_field(
            rows,
            "vlricms",
        )

        valor_pis = cls._sum_field(
            rows,
            "vlrpis",
        )

        valor_cofins = cls._sum_field(
            rows,
            "vlrcofins",
        )

        valor_gasto_fixo = cls._sum_field(
            rows,
            "vlr_gasto_fixo",
        )

        valor_irpj_cssl = cls._sum_field(
            rows,
            "vlr_irpj_cssl",
        )

        valor_comissao = cls._sum_field(
            rows,
            "vlr_comissao",
        )

        valor_gasto_total = cls._sum_field(
            rows,
            "vlr_gasto_total",
        )

        valor_liquido = cls._sum_field(
            rows,
            "vlr_liquido",
        )

        valor_impostos = (
            valor_icms
            + valor_pis
            + valor_cofins
        )

        kpis: dict[str, Any] = {
            "quantidade_notas": len(nunotas),

            "valor_nota": cls._money(
                valor_nota
            ),

            "valor_icms": cls._money(
                valor_icms
            ),

            "valor_pis": cls._money(
                valor_pis
            ),

            "valor_cofins": cls._money(
                valor_cofins
            ),

            "valor_impostos": cls._money(
                valor_impostos
            ),

            "perc_gasto_fixo": 17.00,
            "perc_irpj_cssl": 3.35,
            "perc_comissao": 3.50,

            "valor_gasto_fixo": cls._money(
                valor_gasto_fixo
            ),

            "valor_irpj_cssl": cls._money(
                valor_irpj_cssl
            ),

            "valor_comissao": cls._money(
                valor_comissao
            ),

            "valor_gasto_total": cls._money(
                valor_gasto_total
            ),

            "valor_liquido": cls._money(
                valor_liquido
            ),
        }

        if incluir_custo:
            custo_medio_sem_icms_total = (
                cls._sum_field(
                    rows,
                    "custo_medio_sem_icms_total",
                )
            )

            custo_formatado = cls._money(
                custo_medio_sem_icms_total
            )

            kpis[
                "custo_medio_sem_icms_total"
            ] = custo_formatado

            # Alias para manter compatibilidade
            # com componentes que usam custo_total.
            kpis["custo_total"] = custo_formatado

        return kpis

    @classmethod
    def _sum_field(
        cls,
        rows: list[dict[str, Any]],
        field: str,
    ) -> Decimal:
        total = cls.ZERO

        for row in rows:
            total += cls._to_decimal(
                row.get(field)
            )

        return total

    @classmethod
    def _to_decimal(
        cls,
        value: Any,
    ) -> Decimal:
        if value is None:
            return cls.ZERO

        if isinstance(value, Decimal):
            return value

        if isinstance(
            value,
            (int, float),
        ):
            return Decimal(str(value))

        value_text = str(value).strip()

        if not value_text:
            return cls.ZERO

        if "," in value_text:
            if "." in value_text:
                value_text = value_text.replace(
                    ".",
                    "",
                )

            value_text = value_text.replace(
                ",",
                ".",
            )

        try:
            return Decimal(value_text)

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            return cls.ZERO

    @classmethod
    def _money(
        cls,
        value: Decimal,
    ) -> float:
        rounded_value = value.quantize(
            cls.CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        return float(rounded_value)