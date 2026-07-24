from decimal import Decimal
from typing import Any

import polars as pl

from app.analytics.common import (
    create_frame,
    sum_column,
    to_float,
)


"""
TOPs de bonificação.

Mantidas explícitas para o caso de a query
passar a trazer outras operações no futuro.
"""
TOPS_BONIFICACAO = {
    1151,
}


class BonificadosAnalytics:
    @classmethod
    def build_kpis(
        cls,
        *,
        bonificados: list[dict[str, Any]],
    ) -> dict[str, float]:
        frame = create_frame(bonificados)

        if frame.is_empty():
            return cls._empty_kpis()

        total = sum_column(
            frame,
            "vlrnota",
        )

        custo_total = cls._calculate_cost(frame)

        return {
            "total": to_float(total),
            "custo_total": to_float(
                custo_total
            ),
            "resultado_apos_custo": to_float(
                total - custo_total
            ),
        }

    @staticmethod
    def _calculate_cost(
        frame: pl.DataFrame,
    ) -> Decimal:
        if (
            "custo_medio_sem_icms_total"
            not in frame.columns
        ):
            return Decimal("0")

        return sum_column(
            frame,
            "custo_medio_sem_icms_total",
        )

    @staticmethod
    def _empty_kpis() -> dict[str, float]:
        return {
            "total": 0.0,
            "custo_total": 0.0,
            "resultado_apos_custo": 0.0,
        }