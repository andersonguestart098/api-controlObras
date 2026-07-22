from typing import Any

import polars as pl

from app.analytics.common import create_frame, sum_column


class RemessasAnalytics:
    @classmethod
    def build_kpis(
        cls,
        *,
        remessas: list[dict[str, Any]],
        itens_remessas: list[dict[str, Any]],
    ) -> dict[str, float]:
        remessas_frame = create_frame(remessas)
        itens_frame = create_frame(itens_remessas)

        total_remessas = sum_column(
            remessas_frame,
            "vlrnota",
        )

        if itens_frame.is_empty():
            return {
                "total_faturamento": float(total_remessas),
                "total_entregue": 0.0,
                "saldo": 0.0,
                "custo_total": 0.0,
                "custo_entregue": 0.0,
                "saldo_custo": 0.0,
            }

        itens = cls._remove_total_row(itens_frame)

        return {
            # Valor oficial da remessa vem da consulta remessas.sql
            "total_faturamento": float(total_remessas),

            # Entregas, saldos e custos vêm de itens_remessas.sql
            "total_entregue": float(
                sum_column(
                    itens,
                    "vlr_entregue_item",
                )
            ),
            "saldo": float(
                sum_column(
                    itens,
                    "vlr_saldo_item",
                )
            ),
            "custo_total": float(
                sum_column(
                    itens,
                    "custo_total",
                )
            ),
            "custo_entregue": float(
                sum_column(
                    itens,
                    "custo_entregue",
                )
            ),
            "saldo_custo": float(
                sum_column(
                    itens,
                    "custo_pendente",
                )
            ),
        }

    @staticmethod
    def _remove_total_row(
        frame: pl.DataFrame,
    ) -> pl.DataFrame:
        if "status_item" not in frame.columns:
            return frame

        return frame.filter(
            pl.col("status_item")
            .fill_null("")
            .str.to_uppercase()
            != "TOTAL"
        )