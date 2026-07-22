from typing import Any

from app.analytics.impostos import ImpostosAnalytics
from app.analytics.interno_obras import InternoObrasAnalytics
from app.analytics.remessas import RemessasAnalytics
from app.analytics.vendas import VendasAnalytics


class DashboardAnalytics:
    @staticmethod
    def build_kpis(
        *,
        notas: list[dict[str, Any]],
        itens_notas: list[dict[str, Any]],
        interno_obras: list[dict[str, Any]],
        remessas: list[dict[str, Any]],
        itens_remessas: list[dict[str, Any]],
        notas_impostos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "vendas": VendasAnalytics.build_kpis(
                notas=notas,
                itens_notas=itens_notas,
            ),
            "interno_obras": (
                InternoObrasAnalytics.build_kpis(
                    interno_obras
                )
            ),
            "remessa_futura": (
                RemessasAnalytics.build_kpis(
                    remessas=remessas,
                    itens_remessas=itens_remessas,
                )
            ),
            "impostos": ImpostosAnalytics.build_kpis(
                notas_impostos
            ),
        }