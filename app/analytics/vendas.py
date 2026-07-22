from decimal import Decimal
from typing import Any

import polars as pl

from app.analytics.common import (
    create_frame,
    sum_column,
    to_float,
)


TOPS_VENDA = {
    1101,
    1164,
    1166,
}

TOPS_DEVOLUCAO = {
    1201,
    1202,
    1257,
    1206,
}


class VendasAnalytics:
    @classmethod
    def build_kpis(
        cls,
        *,
        notas: list[dict[str, Any]],
        itens_notas: list[dict[str, Any]],
    ) -> dict[str, float]:
        notas_frame = create_frame(notas)
        itens_frame = create_frame(itens_notas)

        if notas_frame.is_empty():
            return cls._empty_kpis()

        vendas = notas_frame.filter(
            pl.col("codtipoper").is_in(TOPS_VENDA)
        )

        devolucoes = notas_frame.filter(
            pl.col("codtipoper").is_in(TOPS_DEVOLUCAO)
        )

        total_vendas = sum_column(
            vendas,
            "vlrnota",
        )

        total_devolucoes = sum_column(
            devolucoes,
            "vlrnota",
        )

        custo_total_vendas = cls._calculate_sales_cost(
            itens_frame
        )

        return {
            "total_vendas": to_float(total_vendas),
            "total_devolucoes": to_float(
                total_devolucoes
            ),
            "vendas_liquidas": to_float(
                total_vendas - total_devolucoes
            ),
            "custo_total": to_float(
                custo_total_vendas
            ),
        }

    @staticmethod
    def _calculate_sales_cost(
        frame: pl.DataFrame,
    ) -> Decimal:
        if frame.is_empty():
            return Decimal("0")

        vendas = frame.filter(
            pl.col("codtipoper").is_in(TOPS_VENDA)
        )

        return sum_column(
            vendas,
            "custo_medio_sem_icms_total",
        )

    @staticmethod
    def _empty_kpis() -> dict[str, float]:
        return {
            "total_vendas": 0.0,
            "total_devolucoes": 0.0,
            "vendas_liquidas": 0.0,
            "custo_total": 0.0,
        }