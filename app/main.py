from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes import (
    auth,
    dashboard,
    health,
    queries,
)
from app.core.config import get_settings
from app.db.mongodb import (
    connect_mongodb,
    disconnect_mongodb,
)
from app.jobs.scheduler import (
    start_scheduler,
    stop_scheduler,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.mongodb_enabled:
        await connect_mongodb()

    start_scheduler()

    try:
        yield
    finally:
        stop_scheduler()

        if settings.mongodb_enabled:
            await disconnect_mongodb()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    health.router,
    prefix="/api/v1",
)

app.include_router(
    auth.router,
    prefix="/api/v1",
)

app.include_router(
    queries.router,
    prefix="/api/v1",
)

app.include_router(
    dashboard.router,
    prefix="/api/v1",
)