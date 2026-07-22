from typing import Any

from app.analytics.common import create_frame, sum_column


class InternoObrasAnalytics:
    @classmethod
    def build_kpis(
        cls,
        interno_obras: list[dict[str, Any]],
    ) -> dict[str, float]:
        frame = create_frame(interno_obras)

        if frame.is_empty():
            return cls._empty_kpis()

        total = sum_column(
            frame,
            "vlrnota",
        )

        return {
            "total": float(total),
        }

    @staticmethod
    def _empty_kpis() -> dict[str, float]:
        return {
            "total": 0.0,
        }