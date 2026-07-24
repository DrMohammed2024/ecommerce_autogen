from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.database.session import AsyncSessionFactory
from app.models.common import Currency, OrderStatus
from app.models.customer import Customer
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository


def make_order(
    *,
    created_at: datetime | None = None,
) -> Order:
    """Create one valid order for API read tests."""

    return Order(
        customer_id=uuid4(),
        items=(
            OrderItem(
                product_id=uuid4(),
                sku=f"ORDER-API-{uuid4().hex[:8]}",
                product_name="Order API Product",
                quantity=2,
                unit_price=Decimal("12.50"),
                currency=Currency.USD,
            ),
        ),
        currency=Currency.USD,
        status=OrderStatus.DRAFT,
        notes="Order API test",
        created_at=created_at or datetime.now(UTC),
    )


async def persist_order(order: Order) -> Order:
    """Persist one order for an API test."""

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        return await repository.create(order)


async def persist_customer(customer: Customer) -> Customer:
    """Persist one customer for an API test."""

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        return await repository.create(customer)


async def persist_product(product: Product) -> Product:
    """Persist one product for an API test."""

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        return await repository.create(product)


async def test_get_order_returns_stored_order(
    api_client: AsyncClient,
) -> None:
    order = await persist_order(make_order())

    response = await api_client.get(f"/orders/{order.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(order.id)
    assert data["customer_id"] == str(order.customer_id)
    assert data["currency"] == "USD"
    assert data["status"] == "draft"
    assert data["notes"] == "Order API test"
    assert data["total_amount"] == "25.00"
    assert data["created_at"]

    assert len(data["items"]) == 1

    item = data["items"][0]

    assert item["product_id"] == str(order.items[0].product_id)
    assert item["sku"] == order.items[0].sku
    assert item["product_name"] == "Order API Product"
    assert item["quantity"] == 2
    assert item["unit_price"] == "12.50"
    assert item["currency"] == "USD"
    assert item["line_total"] == "25.00"


async def test_get_unknown_order_returns_not_found(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(f"/orders/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found."}


async def test_list_orders_contains_stored_order(
    api_client: AsyncClient,
) -> None:
    order = await persist_order(make_order())

    response = await api_client.get("/orders?limit=500")

    assert response.status_code == 200

    returned_ids = {returned_order["id"] for returned_order in response.json()}

    assert str(order.id) in returned_ids


async def test_list_orders_uses_stable_creation_order(
    api_client: AsyncClient,
) -> None:
    later_order = await persist_order(
        make_order(
            created_at=datetime(
                2026,
                4,
                2,
                12,
                30,
                tzinfo=UTC,
            )
        )
    )
    earlier_order = await persist_order(
        make_order(
            created_at=datetime(
                2026,
                4,
                1,
                12,
                30,
                tzinfo=UTC,
            )
        )
    )

    response = await api_client.get("/orders?limit=500")

    assert response.status_code == 200

    returned_ids = [returned_order["id"] for returned_order in response.json()]

    assert returned_ids.index(str(earlier_order.id)) < returned_ids.index(str(later_order.id))


async def test_list_orders_respects_limit(
    api_client: AsyncClient,
) -> None:
    await persist_order(
        make_order(
            created_at=datetime(
                2026,
                4,
                1,
                12,
                30,
                tzinfo=UTC,
            )
        )
    )
    await persist_order(
        make_order(
            created_at=datetime(
                2026,
                4,
                2,
                12,
                30,
                tzinfo=UTC,
            )
        )
    )

    response = await api_client.get("/orders?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_orders_rejects_non_positive_limit(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/orders?limit=0")

    assert response.status_code == 422


async def test_create_order_persists_order_and_decrements_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Order Customer",
            email=f"order-{uuid4().hex}@example.com",
        )
    )
    product = await persist_product(
        Product(
            sku=f"POST-ORDER-{uuid4().hex[:8]}",
            name="Stored Product Name",
            unit_price=Decimal("19.95"),
            currency=Currency.USD,
            stock_quantity=10,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 3,
                }
            ],
            "currency": "USD",
            "notes": "Created through API",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["customer_id"] == str(customer.id)
    assert data["currency"] == "USD"
    assert data["status"] == "draft"
    assert data["notes"] == "Created through API"
    assert data["total_amount"] == "59.85"

    item = data["items"][0]

    assert item["product_id"] == str(product.id)
    assert item["sku"] == product.sku
    assert item["product_name"] == "Stored Product Name"
    assert item["quantity"] == 3
    assert item["unit_price"] == "19.95"
    assert item["line_total"] == "59.85"

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_order = await OrderRepository(session).get_by_id(UUID(data["id"]))

    assert stored_product is not None
    assert stored_product.stock_quantity == 7
    assert stored_order is not None
    assert stored_order.customer_id == customer.id


async def test_create_order_rejects_insufficient_stock_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Insufficient Stock Customer",
            email=f"insufficient-{uuid4().hex}@example.com",
        )
    )
    product = await persist_product(
        Product(
            sku=f"LOW-STOCK-{uuid4().hex[:8]}",
            name="Low Stock Product",
            unit_price=Decimal("25.00"),
            currency=Currency.USD,
            stock_quantity=2,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 3,
                }
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 409

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=100)

    assert stored_product is not None
    assert stored_product.stock_quantity == 2
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rejects_missing_product_without_creating_order(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Missing Product Customer",
            email=f"missing-product-{uuid4().hex}@example.com",
        )
    )
    existing_product = await persist_product(
        Product(
            sku=f"EXISTING-{uuid4().hex[:8]}",
            name="Existing Product",
            unit_price=Decimal("18.00"),
            currency=Currency.USD,
            stock_quantity=8,
        )
    )
    missing_product_id = uuid4()

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(existing_product.id),
                    "quantity": 2,
                },
                {
                    "product_id": str(missing_product_id),
                    "quantity": 1,
                },
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 404

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(existing_product.id)
        stored_orders = await OrderRepository(session).list_all(limit=100)

    assert stored_product is not None
    assert stored_product.stock_quantity == 8
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rejects_missing_customer_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    missing_customer_id = uuid4()
    product = await persist_product(
        Product(
            sku=f"NO-CUSTOMER-{uuid4().hex[:8]}",
            name="Customer Validation Product",
            unit_price=Decimal("12.50"),
            currency=Currency.USD,
            stock_quantity=6,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(missing_customer_id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 2,
                }
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 404

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=100)

    assert stored_product is not None
    assert stored_product.stock_quantity == 6
    assert all(order.customer_id != missing_customer_id for order in stored_orders)


async def test_create_order_rejects_currency_mismatch_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Currency Mismatch Customer",
            email=f"currency-mismatch-{uuid4().hex}@example.com",
        )
    )
    product = await persist_product(
        Product(
            sku=f"EUR-PRODUCT-{uuid4().hex[:8]}",
            name="Euro Product",
            unit_price=Decimal("30.00"),
            currency=Currency.EUR,
            stock_quantity=9,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 2,
                }
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 409

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=100)

    assert stored_product is not None
    assert stored_product.stock_quantity == 9
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rejects_inactive_customer_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Inactive Customer",
            email=f"inactive-customer-{uuid4().hex}@example.com",
            is_active=False,
        )
    )
    product = await persist_product(
        Product(
            sku=f"INACTIVE-CUSTOMER-{uuid4().hex[:8]}",
            name="Inactive Customer Product",
            unit_price=Decimal("15.00"),
            currency=Currency.USD,
            stock_quantity=7,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 2,
                }
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 409

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=500)

    assert stored_product is not None
    assert stored_product.stock_quantity == 7
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rejects_inactive_product_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Inactive Product Customer",
            email=f"inactive-product-{uuid4().hex}@example.com",
        )
    )
    product = await persist_product(
        Product(
            sku=f"INACTIVE-PRODUCT-{uuid4().hex[:8]}",
            name="Inactive Product",
            unit_price=Decimal("22.00"),
            currency=Currency.USD,
            stock_quantity=11,
            is_active=False,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 3,
                }
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 409

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=500)

    assert stored_product is not None
    assert stored_product.stock_quantity == 11
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rejects_duplicate_product_without_changing_stock(
    api_client: AsyncClient,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Duplicate Product Customer",
            email=f"duplicate-product-{uuid4().hex}@example.com",
        )
    )
    product = await persist_product(
        Product(
            sku=f"DUPLICATE-{uuid4().hex[:8]}",
            name="Duplicate Product",
            unit_price=Decimal("17.50"),
            currency=Currency.USD,
            stock_quantity=12,
        )
    )

    response = await api_client.post(
        "/orders",
        json={
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 2,
                },
                {
                    "product_id": str(product.id),
                    "quantity": 1,
                },
            ],
            "currency": "USD",
        },
    )

    assert response.status_code == 409

    async with AsyncSessionFactory() as session:
        stored_product = await ProductRepository(session).get_by_id(product.id)
        stored_orders = await OrderRepository(session).list_all(limit=500)

    assert stored_product is not None
    assert stored_product.stock_quantity == 12
    assert all(order.customer_id != customer.id for order in stored_orders)


async def test_create_order_rolls_back_first_stock_change_when_second_change_fails(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer = await persist_customer(
        Customer(
            full_name="Atomic Rollback Customer",
            email=f"atomic-rollback-{uuid4().hex}@example.com",
        )
    )
    first_product = await persist_product(
        Product(
            sku=f"ROLLBACK-FIRST-{uuid4().hex[:8]}",
            name="Rollback First Product",
            unit_price=Decimal("10.00"),
            currency=Currency.USD,
            stock_quantity=10,
        )
    )
    second_product = await persist_product(
        Product(
            sku=f"ROLLBACK-SECOND-{uuid4().hex[:8]}",
            name="Rollback Second Product",
            unit_price=Decimal("20.00"),
            currency=Currency.USD,
            stock_quantity=10,
        )
    )

    original_adjust_stock = ProductRepository.adjust_stock
    adjustment_calls = 0

    async def fail_on_second_adjustment(
        repository: ProductRepository,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal adjustment_calls
        adjustment_calls += 1

        if adjustment_calls == 2:
            raise RuntimeError("Forced failure during second stock adjustment.")

        return await original_adjust_stock(repository, *args, **kwargs)

    monkeypatch.setattr(
        ProductRepository,
        "adjust_stock",
        fail_on_second_adjustment,
    )

    with pytest.raises(
        RuntimeError,
        match="Forced failure during second stock adjustment",
    ):
        await api_client.post(
            "/orders",
            json={
                "customer_id": str(customer.id),
                "items": [
                    {
                        "product_id": str(first_product.id),
                        "quantity": 3,
                    },
                    {
                        "product_id": str(second_product.id),
                        "quantity": 4,
                    },
                ],
                "currency": "USD",
            },
        )

    assert adjustment_calls == 2

    async with AsyncSessionFactory() as session:
        stored_first_product = await ProductRepository(session).get_by_id(first_product.id)
        stored_second_product = await ProductRepository(session).get_by_id(second_product.id)
        stored_orders = await OrderRepository(session).list_all(limit=500)

    assert stored_first_product is not None
    assert stored_second_product is not None

    assert stored_first_product.stock_quantity == 10
    assert stored_second_product.stock_quantity == 10
    assert all(order.customer_id != customer.id for order in stored_orders)
