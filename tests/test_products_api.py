from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.database.commerce_models import ProductRecord
from app.database.session import AsyncSessionFactory

_TEST_SKU_PATTERN = "API-TEST-%"


@pytest.fixture(autouse=True)
async def isolate_product_api_records() -> AsyncIterator[None]:
    """Remove product records created by this API test module."""

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(ProductRecord).where(ProductRecord.sku.like(_TEST_SKU_PATTERN))
        )
        await session.commit()

    yield

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(ProductRecord).where(ProductRecord.sku.like(_TEST_SKU_PATTERN))
        )
        await session.commit()


async def test_create_product_returns_created_product(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-CREATE",
            "name": "API Test Product",
            "description": "Created through the products API.",
            "unit_price": "19.99",
            "currency": "USD",
            "stock_quantity": 12,
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["sku"] == "API-TEST-CREATE"
    assert data["name"] == "API Test Product"
    assert data["unit_price"] == "19.99"
    assert data["currency"] == "USD"
    assert data["stock_quantity"] == 12
    assert data["is_active"] is True
    assert data["id"]
    assert data["created_at"]


async def test_get_product_returns_created_product(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-FETCH",
            "name": "API Fetch Product",
            "unit_price": "7.50",
            "currency": "EUR",
            "stock_quantity": 4,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.get(f"/products/{product_id}")

    assert response.status_code == 200
    assert response.json()["id"] == product_id
    assert response.json()["sku"] == "API-TEST-FETCH"


async def test_list_products_contains_created_product(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-LIST",
            "name": "API List Product",
            "unit_price": "11.25",
            "stock_quantity": 3,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.get("/products?limit=500")

    assert response.status_code == 200
    returned_ids = {product["id"] for product in response.json()}
    assert product_id in returned_ids


async def test_create_product_rejects_duplicate_sku(
    api_client: AsyncClient,
) -> None:
    payload = {
        "sku": "API-TEST-DUPLICATE",
        "name": "API Duplicate Product",
        "unit_price": "15.00",
        "stock_quantity": 1,
    }

    first_response = await api_client.post("/products", json=payload)
    second_response = await api_client.post("/products", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "A product with this SKU already exists."}


async def test_get_unknown_product_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(f"/products/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}


async def test_update_product_changes_mutable_fields(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-PATCH",
            "name": "Product Before Update",
            "description": "Old description",
            "unit_price": "20.00",
            "currency": "USD",
            "stock_quantity": 10,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/products/{product_id}",
        json={
            "name": "Product After Update",
            "description": None,
            "unit_price": "24.99",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == product_id
    assert response.json()["name"] == "Product After Update"
    assert response.json()["description"] is None
    assert response.json()["unit_price"] == "24.99"
    assert response.json()["stock_quantity"] == 10


async def test_adjust_product_stock_increases_quantity(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-STOCK-UP",
            "name": "Stock Increase Product",
            "unit_price": "8.00",
            "stock_quantity": 10,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/products/{product_id}/stock",
        json={"quantity_delta": 5},
    )

    assert response.status_code == 200
    assert response.json()["stock_quantity"] == 15


async def test_adjust_product_stock_decreases_quantity(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-STOCK-DOWN",
            "name": "Stock Decrease Product",
            "unit_price": "8.00",
            "stock_quantity": 10,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/products/{product_id}/stock",
        json={"quantity_delta": -4},
    )

    assert response.status_code == 200
    assert response.json()["stock_quantity"] == 6


async def test_adjust_product_stock_rejects_negative_result(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-STOCK-NEGATIVE",
            "name": "Negative Stock Product",
            "unit_price": "8.00",
            "stock_quantity": 2,
        },
    )
    product_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/products/{product_id}/stock",
        json={"quantity_delta": -3},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "stock quantity cannot be negative."}


async def test_update_product_rejects_duplicate_sku(
    api_client: AsyncClient,
) -> None:
    first_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-PATCH-FIRST",
            "name": "First Patch Product",
            "unit_price": "10.00",
        },
    )
    second_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-PATCH-SECOND",
            "name": "Second Patch Product",
            "unit_price": "10.00",
        },
    )

    response = await api_client.patch(
        f"/products/{second_response.json()['id']}",
        json={"sku": first_response.json()["sku"]},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A product with this SKU already exists."}


async def test_deactivate_product_returns_no_content(
    api_client: AsyncClient,
) -> None:
    create_response = await api_client.post(
        "/products",
        json={
            "sku": "API-TEST-DEACTIVATE",
            "name": "Deactivate Product",
            "unit_price": "9.00",
            "stock_quantity": 3,
        },
    )
    product_id = create_response.json()["id"]

    delete_response = await api_client.delete(f"/products/{product_id}")
    get_response = await api_client.get(f"/products/{product_id}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


async def test_update_unknown_product_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.patch(
        f"/products/{uuid4()}",
        json={"name": "Unknown Product"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}


async def test_adjust_stock_for_unknown_product_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.patch(
        f"/products/{uuid4()}/stock",
        json={"quantity_delta": 1},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}


async def test_delete_unknown_product_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.delete(f"/products/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}
