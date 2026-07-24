from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    """Provide an asynchronous client for API tests."""

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


async def test_health_check_returns_healthy_status(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "available",
    }
