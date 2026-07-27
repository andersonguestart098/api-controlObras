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
    ) -> dict[str, Any]:
        """
        Monta todos os indicadores do dashboard.

        As devoluções de Interno Obras ficam
        separadas das devoluções de vendas normais
        e abatem exclusivamente o Interno Obras.
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
                cls._build_remessa_futura_kpis(
                    remessas=remessas,
                    remessas_transporte=(
                        remessas_transporte
                    ),
                )
            ),

            "remessa_transporte": cls._build_movimento_kpis(
                rows=remessas_transporte,
                incluir_custo=True,
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
        }

    @classmethod
    def _build_remessa_futura_kpis(
        cls,
        *,
        remessas: list[dict[str, Any]],
        remessas_transporte: list[dict[str, Any]],
    ) -> dict[str, float]:
        """
        Mantém o formato de retorno já utilizado
        pelo frontend, mas sem itens_remessas.

        total_faturamento:
            soma das notas TOP 1009.

        total_entregue:
            soma das notas reais TOP 1157.

        custo_entregue:
            custo real das notas TOP 1157.
        """

        total_faturamento = cls._sum_field(
            remessas,
            "vlrnota",
        )

        total_entregue = cls._sum_field(
            remessas_transporte,
            "vlrnota",
        )

        saldo = (
            total_faturamento
            - total_entregue
        )

        custo_entregue = cls._sum_field(
            remessas_transporte,
            "custo_medio_sem_icms_total",
        )

        custo_formatado = cls._money(
            custo_entregue
        )

        return {
            "total_faturamento": cls._money(
                total_faturamento
            ),

            "total_entregue": cls._money(
                total_entregue
            ),

            "saldo": cls._money(
                saldo
            ),

            # Compatibilidade com o frontend atual.
            # Agora representa o custo real das 1157.
            "custo_total": custo_formatado,
            "custo_entregue": custo_formatado,

            # O saldo projetado por item não participa
            # mais do endpoint principal de KPIs.
            "saldo_custo": 0.0,
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