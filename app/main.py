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

API_DESCRIPTION = """
## E-Commerce Autogen API

واجهة برمجية لإدارة العمليات الأساسية لنظام التجارة الإلكترونية.

### الوظائف الحالية

- **Customers:** إنشاء العملاء وعرضهم وتحديثهم وتعطيلهم.
- **Products:** إنشاء المنتجات وتحديثها وإدارة المخزون.
- **Orders:** إنشاء الطلبات وعرض تفاصيلها.
- **Health:** التحقق من جاهزية التطبيق وقاعدة البيانات.

### دورة الاستخدام المقترحة

1. إنشاء عميل.
2. إنشاء منتج وتحديد السعر والمخزون.
3. إنشاء طلب مرتبط بالعميل والمنتجات.
4. التحقق من الطلب والكمية المتبقية في المخزون.

### ملاحظات

هذا الإصدار مخصص للتطوير والاختبار. ستُضاف لاحقًا المصادقة،
والصلاحيات، والدفع، والشحن، والتقارير، والوظائف المتقدمة.
"""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": ("فحص جاهزية التطبيق وإمكانية الاتصال بقاعدة البيانات."),
    },
    {
        "name": "customers",
        "description": ("إدارة بيانات العملاء، بما يشمل الإنشاء والعرض والتحديث والتعطيل."),
    },
    {
        "name": "products",
        "description": ("إدارة المنتجات والأسعار والعملات والكميات المتوفرة في المخزون."),
    },
    {
        "name": "orders",
        "description": ("إنشاء طلبات الشراء وعرضها، مع تحديث المخزون داخل معاملة واحدة."),
    },
]

app = FastAPI(
    title="E-Commerce Autogen API",
    description=API_DESCRIPTION,
    version="0.1.0",
    contact={
        "name": "E-Commerce Autogen Team",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(products_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Check application health",
    description="Report application and database availability.",
)
async def health_check() -> HealthResponse:
    """Report application and database availability."""

    database_is_healthy = await database_health_check()

    return HealthResponse(
        status="ok" if database_is_healthy else "degraded",
        database="available" if database_is_healthy else "unavailable",
    )
