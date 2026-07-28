from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from typing import Any

ZERO = Decimal("0")
CENTAVOS = Decimal("0.01")


class RemessasTransporteAnalytics:
    """
    KPIs das notas filhas TOP 1157.

    A fonte é exclusivamente o cabeçalho
    retornado por remessas_transporte.sql.

    Nada aqui vem de itens_remessas.sql:
    aquela consulta segue sendo usada apenas
    no controle detalhado de remessas.
    """

    @classmethod
    def build_kpis(
        cls,
        rows: list[dict[str, Any]],
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

        valor_impostos = (
            valor_icms
            + valor_pis
            + valor_cofins
        )

        valor_federais = (
            valor_pis
            + valor_cofins
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

        resultado_apos_custo = cls._sum_field(
            rows,
            "resultado_apos_custo",
        )

        custo_medio_sem_icms_total = (
            cls._sum_field(
                rows,
                "custo_medio_sem_icms_total",
            )
        )

        custo_formatado = cls._money(
            custo_medio_sem_icms_total
        )

        return {
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

            "valor_federais": cls._money(
                valor_federais
            ),

            "valor_impostos": cls._money(
                valor_impostos
            ),

            # As 1157 não carregam encargos
            # próprios: gasto fixo, IRPJ/CSLL e
            # comissão já foram calculados na
            # nota-mãe TOP 1009.
            "perc_gasto_fixo": cls._first_percent(
                rows,
                "perc_gasto_fixo",
            ),

            "perc_irpj_cssl": cls._first_percent(
                rows,
                "perc_irpj_cssl",
            ),

            "perc_comissao": cls._first_percent(
                rows,
                "perc_comissao",
            ),

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

            "resultado_apos_custo": cls._money(
                resultado_apos_custo
            ),

            "custo_medio_sem_icms_total": (
                custo_formatado
            ),

            # Alias mantido para os componentes
            # que já consomem custo_total.
            "custo_total": custo_formatado,
        }

    @classmethod
    def _first_percent(
        cls,
        rows: list[dict[str, Any]],
        field: str,
    ) -> float:
        for row in rows:
            value = row.get(field)

            if value is not None:
                return cls._money(
                    cls._to_decimal(value)
                )

        return 0.0

    @classmethod
    def _sum_field(
        cls,
        rows: list[dict[str, Any]],
        field: str,
    ) -> Decimal:
        total = ZERO

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
            return ZERO

        if isinstance(value, Decimal):
            return value

        if isinstance(
            value,
            (int, float),
        ):
            return Decimal(str(value))

        value_text = str(value).strip()

        if not value_text:
            return ZERO

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
            return ZERO

    @staticmethod
    def _money(
        value: Decimal,
    ) -> float:
        rounded_value = value.quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        return float(rounded_value)