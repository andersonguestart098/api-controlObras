from enum import StrEnum

from pydantic import BaseModel, Field


class QueryGranularity(StrEnum):
    PROJETO = "projeto"
    TITULO = "titulo"
    NOTA = "nota"
    ITEM = "item"


class SankhyaQueryDefinition(BaseModel):
    code: str
    name: str
    filename: str
    granularity: QueryGranularity
    expected_columns: list[str] = Field(default_factory=list)
    supports_period: bool = True
    supports_nunota: bool = True
