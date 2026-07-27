from typing import Any

from app.analytics.common import (
    create_frame,
    sum_column,
    to_float,
)


class DevolucoesInternoObrasAnalytics:
    @classmethod
    def build_kpis(
        cls,
        devolucoes: list[dict[str, Any]],
    ) -> dict[str, float | int]:
        frame = create_frame(devolucoes)

        if frame.is_empty():
            return cls._empty_kpis()

        quantidade_notas = len(
            {
                row.get("nunota")
                for row in devolucoes
                if row.get("nunota") is not None
            }
        )

        icms = cls._sum_column(
            frame,
            "vlricms",
        )

        pis = cls._sum_column(
            frame,
            "vlrpis",
        )

        cofins = cls._sum_column(
            frame,
            "vlrcofins",
        )

        federais = round(
            pis + cofins,
            2,
        )

        total_tributos = round(
            icms + pis + cofins,
            2,
        )

        return {
            "quantidade_notas": quantidade_notas,

            "total": cls._sum_column(
                frame,
                "vlrnota",
            ),

            "custo_total": cls._sum_column(
                frame,
                "custo_medio_sem_icms_total",
            ),

            "resultado_apos_custo": (
                cls._sum_column(
                    frame,
                    "resultado_apos_custo",
                )
            ),

            "icms": icms,
            "pis": pis,
            "cofins": cofins,
            "federais": federais,
            "total_tributos": total_tributos,

            "gasto_fixo": cls._sum_column(
                frame,
                "vlr_gasto_fixo",
            ),

            "irpj_cssl": cls._sum_column(
                frame,
                "vlr_irpj_cssl",
            ),

            "comissao": cls._sum_column(
                frame,
                "vlr_comissao",
            ),

            "gasto_total": cls._sum_column(
                frame,
                "vlr_gasto_total",
            ),

            "valor_liquido": cls._sum_column(
                frame,
                "vlr_liquido",
            ),
        }

    @staticmethod
    def _sum_column(
        frame: Any,
        column: str,
    ) -> float:
        if column not in frame.columns:
            return 0.0

        return to_float(
            sum_column(
                frame,
                column,
            )
        )

    @staticmethod
    def _empty_kpis() -> dict[str, float | int]:
        return {
            "quantidade_notas": 0,

            "total": 0.0,
            "custo_total": 0.0,
            "resultado_apos_custo": 0.0,

            "icms": 0.0,
            "pis": 0.0,
            "cofins": 0.0,
            "federais": 0.0,
            "total_tributos": 0.0,

            "gasto_fixo": 0.0,
            "irpj_cssl": 0.0,
            "comissao": 0.0,
            "gasto_total": 0.0,
            "valor_liquido": 0.0,
        }