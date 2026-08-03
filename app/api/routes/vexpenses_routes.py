from datetime import date
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.integrations.vexpenses_client import (
    VExpensesAPIError,
)
from app.services.vexpenses_service import (
    VExpensesService,
    get_vexpenses_service,
)


router = APIRouter(
    prefix="/vexpenses",
    tags=["VExpenses"],
)


@router.get(
    "/projects",
    summary="Listar projetos da VExpenses",
)
async def listar_projetos(
    pagina: int = Query(
        default=1,
        ge=1,
        description="Página consultada na VExpenses.",
    ),
    itens_por_pagina: int = Query(
        default=100,
        ge=1,
        le=100,
        description="Quantidade de projetos por página.",
    ),
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> Any:
    try:
        return await service.listar_projetos(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc

@router.get(
    "/projects/by-integration/{codproj}",
    summary="Buscar projeto pelo CODPROJ do Sankhya",
)
async def buscar_projeto_por_codproj(
    codproj: int,
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> dict[str, Any] | None:
    """
    Retorna o projeto vinculado ou null com HTTP 200.

    Projeto sem vínculo é um estado vazio esperado no dashboard,
    por isso não deve gerar 404.
    """

    try:
        return await service.buscar_projeto_por_codproj(
            codproj=codproj,
        )

    except ValueError:
        return None

    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc

@router.get(
    "/projects/{project_id}",
    summary="Buscar projeto da VExpenses por ID",
)
async def buscar_projeto_por_id(
    project_id: int,
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> Any:
    try:
        return await service.buscar_projeto_por_id(
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


@router.get(
    "/reports/approved",
    summary="Listar relatórios aprovados da VExpenses",
)
async def listar_relatorios_aprovados(
    pagina: int = Query(
        default=1,
        ge=1,
        description="Página consultada na VExpenses.",
    ),
    itens_por_pagina: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Quantidade de relatórios por página.",
    ),
    data_inicial: date | None = Query(
        default=None,
        description=(
            "Data inicial da aprovação no formato YYYY-MM-DD."
        ),
    ),
    data_final: date | None = Query(
        default=None,
        description=(
            "Data final da aprovação no formato YYYY-MM-DD."
        ),
    ),
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> Any:
    try:
        return await service.listar_relatorios_aprovados(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
            data_inicial=data_inicial,
            data_final=data_final,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


@router.get(
    "/summary",
    summary="Resumo da VExpenses por projeto",
)
async def get_vexpenses_summary(
    project_id: int = Query(
        ...,
        gt=0,
        description=(
            "ID do projeto cadastrado na VExpenses. "
            "É comparado com course_id das despesas."
        ),
    ),
    data_inicial: date | None = Query(
        default=None,
        description=(
            "Data inicial da despesa no formato YYYY-MM-DD."
        ),
    ),
    data_final: date | None = Query(
        default=None,
        description=(
            "Data final da despesa no formato YYYY-MM-DD."
        ),
    ),
    incluir_movimentos: bool = Query(
        default=False,
        description=(
            "Inclui a lista completa das despesas. "
            "Mantenha falso para uma resposta mais leve."
        ),
    ),
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> dict[str, Any]:
    try:
        return await service.obter_resumo_dashboard(
            project_id=project_id,
            data_inicial=data_inicial,
            data_final=data_final,
            incluir_movimentos=incluir_movimentos,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


def _converter_erro_vexpenses(
    exc: VExpensesAPIError,
) -> HTTPException:
    upstream_status = exc.status_code

    if upstream_status == 429:
        response_status = (
            status.HTTP_429_TOO_MANY_REQUESTS
        )
    elif upstream_status == 404:
        response_status = status.HTTP_404_NOT_FOUND
    elif upstream_status in {400, 422}:
        response_status = status.HTTP_400_BAD_REQUEST
    else:
        response_status = status.HTTP_502_BAD_GATEWAY

    return HTTPException(
        status_code=response_status,
        detail={
            "mensagem": str(exc),
            "origem": "VExpenses",
            "status_vexpenses": upstream_status,
            "resposta_vexpenses": exc.response_data,
        },
    )