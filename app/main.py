from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.customers import router as customers_router
from app.api.orders import router as orders_router
from app.api.products import router as products_router
from app.config import get_settings
from app.database import (
    database_health_check,
    dispose_database,
    init_database,
)


class HealthResponse(BaseModel):
    """Health-check response returned by the API."""

    status: str
    database: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and dispose application resources."""

    _ = app
    await init_database()

    try:
        yield
    finally:
        await dispose_database()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(products_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """Report application and database availability."""

    database_is_healthy = await database_health_check()

    return HealthResponse(
        status="ok" if database_is_healthy else "degraded",
        database="available" if database_is_healthy else "unavailable",
    )
