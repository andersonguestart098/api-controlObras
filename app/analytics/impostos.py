from decimal import Decimal
from typing import Any

import polars as pl

from app.analytics.common import (
    create_frame,
    sum_column,
    to_float,
)


class ImpostosAnalytics:
    @classmethod
    def build_kpis(
        cls,
        notas_impostos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        frame = create_frame(notas_impostos)

        if frame.is_empty():
            return cls._empty_kpis()

        vendas = frame.filter(
            (pl.col("tipo_movimento") == "VENDA")
            & (pl.col("interno_obras") == "N")
        )

        devolucoes = frame.filter(
            pl.col("tipo_movimento") == "DEVOLUCAO"
        )

        interno_obras = frame.filter(
            (pl.col("tipo_movimento") == "VENDA")
            & (pl.col("interno_obras") == "S")
        )

        remessas = frame.filter(
            pl.col("tipo_movimento") == "REMESSA"
        )

        valores_vendas = cls._calculate_group(vendas)
        valores_devolucoes = cls._calculate_group(devolucoes)
        valores_interno_obras = cls._calculate_group(
            interno_obras
        )
        valores_remessas = cls._calculate_group(remessas)

        consolidado = {
            "icms": (
                valores_vendas["icms"]
                + valores_interno_obras["icms"]
                + valores_remessas["icms"]
                - valores_devolucoes["icms"]
            ),
            "pis": (
                valores_vendas["pis"]
                + valores_interno_obras["pis"]
                + valores_remessas["pis"]
                - valores_devolucoes["pis"]
            ),
            "cofins": (
                valores_vendas["cofins"]
                + valores_interno_obras["cofins"]
                + valores_remessas["cofins"]
                - valores_devolucoes["cofins"]
            ),
            "federais": (
                valores_vendas["federais"]
                + valores_interno_obras["federais"]
                + valores_remessas["federais"]
                - valores_devolucoes["federais"]
            ),
            "total_tributos": (
                valores_vendas["total_tributos"]
                + valores_interno_obras["total_tributos"]
                + valores_remessas["total_tributos"]
                - valores_devolucoes["total_tributos"]
            ),
            "comissao": (
                valores_vendas["comissao"]
                + valores_interno_obras["comissao"]
                + valores_remessas["comissao"]
                - valores_devolucoes["comissao"]
            ),
        }

        return {
            "vendas": cls._serialize_group(
                valores_vendas
            ),
            "devolucoes": cls._serialize_group(
                valores_devolucoes
            ),
            "interno_obras": cls._serialize_group(
                valores_interno_obras
            ),
            "remessa_futura": cls._serialize_group(
                valores_remessas
            ),
            "consolidado_liquido": cls._serialize_group(
                consolidado
            ),
        }

    @staticmethod
    def _calculate_group(
        frame: pl.DataFrame,
    ) -> dict[str, Decimal]:
        return {
            "icms": sum_column(
                frame,
                "vlr_icms",
            ),
            "pis": sum_column(
                frame,
                "vlr_pis",
            ),
            "cofins": sum_column(
                frame,
                "vlr_cofins",
            ),
            "federais": sum_column(
                frame,
                "vlr_tributos_federais",
            ),
            "total_tributos": sum_column(
                frame,
                "vlr_total_tributos",
            ),
            "comissao": sum_column(
                frame,
                "vlr_comissao",
            ),
        }

    @staticmethod
    def _serialize_group(
        group: dict[str, Decimal],
    ) -> dict[str, float]:
        return {
            key: to_float(value)
            for key, value in group.items()
        }

    @staticmethod
    def _empty_group() -> dict[str, float]:
        return {
            "icms": 0.0,
            "pis": 0.0,
            "cofins": 0.0,
            "federais": 0.0,
            "total_tributos": 0.0,
            "comissao": 0.0,
        }

    @classmethod
    def _empty_kpis(cls) -> dict[str, Any]:
        return {
            "vendas": cls._empty_group(),
            "devolucoes": cls._empty_group(),
            "interno_obras": cls._empty_group(),
            "remessa_futura": cls._empty_group(),
            "consolidado_liquido": cls._empty_group(),
        }