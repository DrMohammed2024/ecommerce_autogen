import asyncio

from app.database import database_health_check, dispose_database, init_database


async def main() -> None:
    """Initialize and verify the local SQLite database."""

    try:
        await init_database()
        is_healthy = await database_health_check()

        if not is_healthy:
            raise RuntimeError("Database health check failed.")

        print("DATABASE INITIALIZED")
        print("DATABASE HEALTH CHECK OK")
    finally:
        await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
