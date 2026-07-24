from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from typing import Any


class EntradasAnalytics:
    ZERO = Decimal("0")
    CENTAVOS = Decimal("0.01")

    @classmethod
    def build_kpis(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        notas = {
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

        return {
            "quantidade_notas": len(notas),
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
        rounded = value.quantize(
            cls.CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        return float(rounded)