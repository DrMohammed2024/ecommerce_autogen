from sqlalchemy import select, text

from app.database import (
    AsyncSessionFactory,
    SchemaVersion,
    database_health_check,
    dispose_database,
    init_database,
)


async def test_database_initialization() -> None:
    await init_database()

    assert await database_health_check() is True


async def test_database_executes_query() -> None:
    await init_database()

    async with AsyncSessionFactory() as session:
        result = await session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


async def test_schema_version_is_registered() -> None:
    await init_database()

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(SchemaVersion).where(SchemaVersion.version == "0.1.0")
        )
        schema_version = result.scalar_one_or_none()

    assert schema_version is not None
    assert schema_version.version == "0.1.0"


async def test_dispose_database() -> None:
    await init_database()
    await dispose_database()

    assert await database_health_check() is True

    await dispose_database()