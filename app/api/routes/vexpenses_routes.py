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


# ============================================================
# PROJETOS
# ============================================================

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
    Busca um projeto pelo integration_id cadastrado na VExpenses.

    Exemplo:
        CODPROJ Sankhya: 10040000
        ID interno VExpenses: 2211713
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


# ============================================================
# DESPESAS
# ============================================================

@router.get(
    "/expenses",
    summary="Listar despesas diretamente da VExpenses",
)
async def listar_despesas(
    pagina: int = Query(
        default=1,
        ge=1,
        description="Página consultada na VExpenses.",
    ),
    itens_por_pagina: int = Query(
        default=100,
        ge=1,
        le=100,
        description="Quantidade de despesas por página.",
    ),
    project_id: int | None = Query(
        default=None,
        gt=0,
        description=(
            "ID interno do projeto na VExpenses. "
            "É comparado com course_id da despesa."
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
    somente_com_projeto: bool = Query(
        default=True,
        description=(
            "Quando verdadeiro, retorna apenas despesas que "
            "possuem course_id preenchido."
        ),
    ),
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> Any:
    """
    Lista despesas diretamente pelo endpoint /expenses.

    Não exige que a despesa esteja:
    - em relatório;
    - enviada;
    - aprovada;
    - reembolsada.

    Quando project_id for informado, somente despesas cujo
    course_id seja igual ao projeto serão retornadas.
    """

    try:
        return await service.listar_despesas(
            pagina=pagina,
            itens_por_pagina=itens_por_pagina,
            project_id=project_id,
            data_inicial=data_inicial,
            data_final=data_final,
            somente_com_projeto=somente_com_projeto,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


@router.get(
    "/expenses/{expense_id}",
    summary="Buscar uma despesa da VExpenses por ID",
)
async def buscar_despesa_por_id(
    expense_id: int,
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> Any:
    try:
        return await service.buscar_despesa_por_id(
            expense_id=expense_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


# ============================================================
# DASHBOARD
# ============================================================

@router.get(
    "/summary",
    summary="Resumo de despesas da VExpenses por projeto",
)
async def get_vexpenses_summary(
    project_id: int = Query(
        ...,
        gt=0,
        description=(
            "ID interno do projeto na VExpenses. "
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
            "Inclui a lista completa das despesas na resposta."
        ),
    ),
    service: VExpensesService = Depends(
        get_vexpenses_service
    ),
) -> dict[str, Any]:
    """
    Gera o resumo diretamente pelas despesas.

    Não consulta relatórios aprovados.

    Uma despesa entra no resumo quando:
        expense.course_id == project_id

    O status de aprovação do relatório não é considerado.
    """

    try:
        return (
            await service.obter_resumo_despesas_por_projeto(
                project_id=project_id,
                data_inicial=data_inicial,
                data_final=data_final,
                incluir_movimentos=incluir_movimentos,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VExpensesAPIError as exc:
        raise _converter_erro_vexpenses(exc) from exc


# ============================================================
# TRATAMENTO DE ERROS
# ============================================================

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