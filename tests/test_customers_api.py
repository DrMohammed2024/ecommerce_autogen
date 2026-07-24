from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.database.commerce_models import CustomerRecord
from app.database.session import AsyncSessionFactory

_TEST_EMAIL_PATTERN = "api-test-%@example.com"


@pytest.fixture(autouse=True)
async def isolate_customer_api_records() -> AsyncIterator[None]:
    """Remove customer records created by this API test module."""

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(CustomerRecord).where(CustomerRecord.email.like(_TEST_EMAIL_PATTERN))
        )
        await session.commit()

    yield

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(CustomerRecord).where(CustomerRecord.email.like(_TEST_EMAIL_PATTERN))
        )
        await session.commit()


async def test_create_customer_returns_created_customer(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test Customer",
            "email": "api-test-create@example.com",
            "phone": "+15550001111",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["full_name"] == "API Test Customer"
    assert data["email"] == "api-test-create@example.com"
    assert data["phone"] == "+15550001111"
    assert data["is_active"] is True
    assert data["id"]
    assert data["created_at"]


async def test_get_customer_returns_created_customer(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test Fetch",
            "email": "api-test-fetch@example.com",
            "phone": "+15550002222",
        },
    )
    customer_id = create_response.json()["id"]

    response = await api_client.get(f"/customers/{customer_id}")

    assert response.status_code == 200
    assert response.json()["id"] == customer_id
    assert response.json()["email"] == "api-test-fetch@example.com"


async def test_list_customers_contains_created_customer(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test List",
            "email": "api-test-list@example.com",
            "phone": "+15550003333",
        },
    )
    customer_id = create_response.json()["id"]

    response = await api_client.get("/customers?limit=500")

    assert response.status_code == 200
    returned_ids = {customer["id"] for customer in response.json()}
    assert customer_id in returned_ids


async def test_create_customer_rejects_duplicate_email(
    api_client: AsyncClient,
) -> None:
    payload = {
        "full_name": "API Test Duplicate",
        "email": "api-test-duplicate@example.com",
        "phone": "+15550004444",
    }

    first_response = await api_client.post("/customers", json=payload)
    second_response = await api_client.post("/customers", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "A customer with this email already exists."}


async def test_get_unknown_customer_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(f"/customers/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Customer not found."}


async def test_update_customer_changes_mutable_fields(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test Before Update",
            "email": "api-test-update@example.com",
            "phone": "+15550005555",
        },
    )
    customer_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/customers/{customer_id}",
        json={
            "full_name": "API Test After Update",
            "phone": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == customer_id
    assert response.json()["full_name"] == "API Test After Update"
    assert response.json()["phone"] is None
    assert response.json()["email"] == "api-test-update@example.com"


async def test_update_customer_rejects_duplicate_email(
    api_client: AsyncClient,
) -> None:
    first_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test First Customer",
            "email": "api-test-patch-first@example.com",
        },
    )
    second_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test Second Customer",
            "email": "api-test-patch-second@example.com",
        },
    )

    response = await api_client.patch(
        f"/customers/{second_response.json()['id']}",
        json={"email": first_response.json()["email"]},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A customer with this email already exists."}


async def test_deactivate_customer_returns_no_content(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/customers",
        json={
            "full_name": "API Test Deactivate",
            "email": "api-test-deactivate@example.com",
        },
    )
    customer_id = create_response.json()["id"]

    delete_response = await api_client.delete(f"/customers/{customer_id}")
    get_response = await api_client.get(f"/customers/{customer_id}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


async def test_update_unknown_customer_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.patch(
        f"/customers/{uuid4()}",
        json={"full_name": "Unknown Customer"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Customer not found."}


async def test_delete_unknown_customer_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.delete(f"/customers/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Customer not found."}
