from datetime import date

from pydantic import BaseModel, Field, model_validator


class DashboardFilters(BaseModel):
    codproj: int = Field(
        ...,
        gt=0,
        description="Código global do projeto/obra",
    )

    dtneg_inicial: date | None = Field(
        default=None,
        description="Data inicial da negociação",
    )

    dtneg_final: date | None = Field(
        default=None,
        description="Data final da negociação",
    )

    nunota: int | None = Field(
        default=None,
        gt=0,
        description="Número único da nota",
    )

    @model_validator(mode="after")
    def validate_period(self) -> "DashboardFilters":
        if (
            self.dtneg_inicial
            and self.dtneg_final
            and self.dtneg_inicial > self.dtneg_final
        ):
            raise ValueError(
                "dtneg_inicial não pode ser maior que dtneg_final."
            )

        return self

    def as_sankhya_params(self) -> dict[str, object | None]:
        return {
            "CODPROJ": self.codproj,
            "DTNEG_INICIAL": (
                self.dtneg_inicial.isoformat()
                if self.dtneg_inicial
                else None
            ),
            "DTNEG_FINAL": (
                self.dtneg_final.isoformat()
                if self.dtneg_final
                else None
            ),
            "NUNOTA": self.nunota,
        }