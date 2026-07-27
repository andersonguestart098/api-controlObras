from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class DashboardFilters(BaseModel):
    """
    Filtros globais do dashboard.

    O projeto é obrigatório.
    O período é opcional.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    codproj: int = Field(
        gt=0,
    )

    dtneg_inicial: date | None = None
    dtneg_final: date | None = None