from pydantic import BaseModel


class MaoObraLinhaPreview(BaseModel):
    linha: int

    codproj: int | None = None
    valor_acumulado: float | None = None

    valida: bool
    erro: str | None = None


class MaoObraPreviewResponse(BaseModel):
    arquivo: str
    aba: str | None = None

    total_linhas: int
    total_validas: int
    total_invalidas: int

    valor_total_valido: float

    linhas: list[MaoObraLinhaPreview]


class MaoObraResultadoLinha(BaseModel):
    linha: int

    codproj: int | None = None
    valor_acumulado: float | None = None

    sucesso: bool

    codigo_pedido: str | None = None
    erro: str | None = None


class MaoObraImportacaoResponse(BaseModel):
    arquivo: str

    total_linhas: int
    total_validas: int
    total_invalidas: int

    total_processadas: int
    total_sucesso: int
    total_erros: int

    valor_total_processado: float

    resultados: list[MaoObraResultadoLinha]