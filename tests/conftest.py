from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.database.init_db import init_database
from app.main import app


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    """Provide an initialized asynchronous API test client."""

    await init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client
