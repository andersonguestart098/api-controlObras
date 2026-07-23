from typing import Any

from app.analytics.common import (
    create_frame,
    sum_column,
    to_float,
)


class InternoObrasAnalytics:
    @classmethod
    def build_kpis(
        cls,
        interno_obras: list[dict[str, Any]],
    ) -> dict[str, float]:
        frame = create_frame(
            interno_obras
        )

        if frame.is_empty():
            return cls._empty_kpis()

        total = sum_column(
            frame,
            "vlrnota",
        )

        custo_total = sum_column(
            frame,
            "custo_medio_sem_icms_total",
        )

        resultado_apos_custo = sum_column(
            frame,
            "resultado_apos_custo",
        )

        return {
            "total": to_float(
                total
            ),
            "custo_total": to_float(
                custo_total
            ),
            "resultado_apos_custo": to_float(
                resultado_apos_custo
            ),
        }

    @staticmethod
    def _empty_kpis() -> dict[str, float]:
        return {
            "total": 0.0,
            "custo_total": 0.0,
            "resultado_apos_custo": 0.0,
        }