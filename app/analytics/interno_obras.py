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
        *,
        interno_obras: list[dict[str, Any]],
        devolucoes_interno_obras: list[
            dict[str, Any]
        ],
    ) -> dict[str, float]:
        """
        Calcula os valores brutos, as devoluções
        vinculadas ao Interno Obras e o resultado
        líquido da operação.
        """

        # Interno Obras bruto
        total_bruto = cls._sum_rows(
            interno_obras,
            "vlrnota",
        )

        custo_bruto = cls._sum_rows(
            interno_obras,
            "custo_medio_sem_icms_total",
        )

        resultado_apos_custo_bruto = (
            cls._sum_rows(
                interno_obras,
                "resultado_apos_custo",
            )
        )

        # Devoluções vinculadas ao Interno Obras
        total_devolucoes = cls._sum_rows(
            devolucoes_interno_obras,
            "vlrnota",
        )

        custo_devolucoes = cls._sum_rows(
            devolucoes_interno_obras,
            "custo_medio_sem_icms_total",
        )

        resultado_apos_custo_devolucoes = (
            cls._sum_rows(
                devolucoes_interno_obras,
                "resultado_apos_custo",
            )
        )

        # Interno Obras líquido
        total_liquido = round(
            total_bruto - total_devolucoes,
            2,
        )

        custo_liquido = round(
            custo_bruto - custo_devolucoes,
            2,
        )

        resultado_apos_custo_liquido = round(
            resultado_apos_custo_bruto
            - resultado_apos_custo_devolucoes,
            2,
        )

        return {
            # Bruto
            "total_bruto": total_bruto,
            "custo_bruto": custo_bruto,
            "resultado_apos_custo_bruto": (
                resultado_apos_custo_bruto
            ),

            # Devoluções
            "total_devolucoes": (
                total_devolucoes
            ),
            "custo_devolucoes": (
                custo_devolucoes
            ),
            "resultado_apos_custo_devolucoes": (
                resultado_apos_custo_devolucoes
            ),

            # Líquido
            #
            # Mantemos os nomes antigos para
            # não quebrar o frontend.
            "total": total_liquido,
            "custo_total": custo_liquido,
            "resultado_apos_custo": (
                resultado_apos_custo_liquido
            ),
        }

    @staticmethod
    def _sum_rows(
        rows: list[dict[str, Any]],
        column: str,
    ) -> float:
        """
        Soma uma coluna, retornando zero quando
        não houver linhas ou quando a coluna não
        estiver presente no DataFrame.
        """

        if not rows:
            return 0.0

        frame = create_frame(rows)

        if frame.is_empty():
            return 0.0

        if column not in frame.columns:
            return 0.0

        total = sum_column(
            frame,
            column,
        )

        return to_float(total)