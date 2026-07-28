from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from typing import Any

ZERO = Decimal("0")
CENTAVOS = Decimal("0.01")


class RemessasAnalytics:
    """
    KPIs da Remessa futura (notas-mãe TOP 1009).

    Duas fontes, ambas de cabeçalho:

    - remessas.sql:
      valor faturado e custo PRÓPRIO da 1009.

    - remessas_transporte.sql:
      valor e custo já entregues pelas notas
      filhas TOP 1157.

    itens_remessas.sql não entra aqui.
    Ele fica reservado ao controle detalhado
    de remessas, nos componentes de baixo.
    """

    @classmethod
    def build_kpis(
        cls,
        *,
        remessas: list[dict[str, Any]],
        remessas_transporte: list[dict[str, Any]],
    ) -> dict[str, float]:
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

        # Custo da própria nota-mãe.
        custo_total = cls._sum_field(
            remessas,
            "custo_medio_sem_icms_total",
        )

        # Custo baixado pelas notas filhas.
        custo_entregue = cls._sum_field(
            remessas_transporte,
            "custo_medio_sem_icms_total",
        )

        saldo_custo = (
            custo_total
            - custo_entregue
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

            "custo_total": cls._money(
                custo_total
            ),

            "custo_entregue": cls._money(
                custo_entregue
            ),

            "saldo_custo": cls._money(
                saldo_custo
            ),
        }

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