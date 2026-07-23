from sqlalchemy import select, text

from app.database.audit_models import GovernanceAuditRecord
from app.database.base import Base
from app.database.commerce_models import (
    CustomerRecord,
    OrderItemRecord,
    OrderRecord,
    PaymentRecord,
    ProductRecord,
)
from app.database.models import SchemaVersion
from app.database.session import AsyncSessionFactory, engine


async def init_database() -> None:
    """Create local database tables and register the schema version."""

    _ = (
        GovernanceAuditRecord,
        CustomerRecord,
        ProductRecord,
        OrderRecord,
        OrderItemRecord,
        PaymentRecord,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("SELECT 1"))

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(SchemaVersion).where(SchemaVersion.version == "0.1.0")
        )
        existing_version = result.scalar_one_or_none()

        if existing_version is None:
            session.add(SchemaVersion(version="0.1.0"))
            await session.commit()


async def database_health_check() -> bool:
    """Return True when the local database accepts a simple query."""

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_database() -> None:
    """Close all database connections held by the engine."""

    await engine.dispose()
