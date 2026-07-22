from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import validar_api_key
from app.queries.registry import QUERY_REGISTRY
from app.schemas.filters import DashboardFilters
from app.services.sankhya_query_service import (
    SankhyaQueryService,
    get_sankhya_query_service,
)


router = APIRouter(
    prefix="/sankhya/queries",
    tags=["Sankhya Queries"],
    dependencies=[Depends(validar_api_key)],
)


@router.get("")
async def list_queries() -> list[dict[str, Any]]:
    return [
        definition.model_dump()
        for definition in QUERY_REGISTRY.values()
    ]


@router.post("/{query_code}")
async def execute_query(
    query_code: str,
    filters: DashboardFilters,
    query_service: SankhyaQueryService = Depends(
        get_sankhya_query_service
    ),
) -> dict[str, Any]:
    definition = QUERY_REGISTRY.get(query_code)

    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consulta '{query_code}' não encontrada.",
        )

    rows = await query_service.execute_query(
        definition=definition,
        filters=filters,
    )

    return {
        "query": definition.code,
        "name": definition.name,
        "granularity": definition.granularity,
        "count": len(rows),
        "filters": filters.model_dump(mode="json"),
        "data": rows,
    }