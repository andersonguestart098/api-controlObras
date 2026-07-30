from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import validar_api_key
from app.schemas.filters import DashboardFilters
from app.services.dashboard_service import (
    DashboardService,
    get_dashboard_service,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(validar_api_key)],
)


@router.post("/kpis")
async def load_dashboard_kpis(
    filters: DashboardFilters,
    service: DashboardService = Depends(
        get_dashboard_service
    ),
) -> dict[str, Any]:
    return await service.get_kpis(filters)

@router.post("/remessas")
async def load_dashboard_remessas(
    filters: DashboardFilters,
    service: DashboardService = Depends(
        get_dashboard_service
    ),
) -> dict[str, Any]:
    return await service.get_remessas_control(
        filters
    )

@router.get("/movimentos")
async def get_movimentos(
    filters: DashboardFilters = Depends(),
    dashboard_service: DashboardService = Depends(
        get_dashboard_service
    ),
) -> dict[str, Any]:
    return await dashboard_service.get_movimentos(
        filters
    )

@router.post("/pagamentos")
async def get_pagamentos(
    filters: DashboardFilters,
    dashboard_service: DashboardService = Depends(
        get_dashboard_service
    ),
) -> dict[str, Any]:
    return await dashboard_service.get_pagamentos(
        filters
    )

@router.post("/raw")
async def load_dashboard_raw(
    filters: DashboardFilters,
    service: DashboardService = Depends(
        get_dashboard_service
    ),
) -> dict[str, Any]:
    return await service.load_all_raw(filters)

