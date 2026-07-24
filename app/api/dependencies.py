from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionFactory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide one database session to an API request."""

    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
