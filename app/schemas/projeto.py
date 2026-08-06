# app/schemas/projeto.py

from pydantic import BaseModel


class ProjetoFiltroResponse(BaseModel):
    codproj: int
    identificacao: str | None = None
    abreviatura: str | None = None
    nome_projeto: str
    label_projeto: str