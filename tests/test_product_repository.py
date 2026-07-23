from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.database.commerce_models import ProductRecord
from app.database.init_db import init_database
from app.database.session import AsyncSessionFactory
from app.models.common import Currency
from app.models.product import Product
from app.repositories import ProductRepository

TEST_SKU_PREFIX = "repo-product-test-"


def make_product(
    suffix: str,
    *,
    stock_quantity: int = 10,
    is_active: bool = True,
) -> Product:
    """Create one valid product for repository tests."""

    return Product(
        sku=f"{TEST_SKU_PREFIX}{suffix}",
        name=f"Product {suffix}",
        description=f"Repository test product {suffix}",
        unit_price=Decimal("19.99"),
        currency=Currency.USD,
        stock_quantity=stock_quantity,
        is_active=is_active,
    )


async def clean_test_products() -> None:
    """Delete only products created by this test module."""

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(ProductRecord).where(
                ProductRecord.sku.like(f"{TEST_SKU_PREFIX}%")
            )
        )
        await session.commit()


@pytest.fixture(autouse=True)
async def initialize_product_database() -> AsyncIterator[None]:
    """Initialize the database and isolate repository test records."""

    await init_database()
    await clean_test_products()

    yield

    await clean_test_products()


async def test_create_persists_product() -> None:
    product = make_product("create")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        created = await repository.create(product)
        stored = await repository.get_by_id(product.id)

    assert created == product
    assert stored == product
    assert created.created_at.tzinfo is not None
    assert created.created_at.utcoffset() == UTC.utcoffset(created.created_at)


async def test_get_by_id_returns_product() -> None:
    product = make_product("get-by-id")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)
        stored = await repository.get_by_id(product.id)

    assert stored is not None
    assert stored.id == product.id
    assert stored.sku == product.sku


async def test_get_by_sku_returns_product() -> None:
    product = make_product("get-by-sku")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)
        stored = await repository.get_by_sku(product.sku)

    assert stored is not None
    assert stored.id == product.id
    assert stored.sku == product.sku


async def test_get_by_id_returns_none_for_unknown_product() -> None:
    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        stored = await repository.get_by_id(uuid4())

    assert stored is None


async def test_get_by_sku_returns_none_for_unknown_product() -> None:
    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        stored = await repository.get_by_sku(
            f"{TEST_SKU_PREFIX}unknown"
        )

    assert stored is None


async def test_list_active_returns_only_active_products() -> None:
    active_product = make_product("list-active")
    inactive_product = make_product(
        "list-inactive",
        is_active=False,
    )

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(active_product)
        await repository.create(inactive_product)
        products = await repository.list_active()

    returned_ids = {product.id for product in products}

    assert active_product.id in returned_ids
    assert inactive_product.id not in returned_ids


async def test_update_changes_only_mutable_product_fields() -> None:
    original = make_product("update-original")
    replacement = Product(
        id=uuid4(),
        sku=f"{TEST_SKU_PREFIX}update-new",
        name="Updated Product",
        description="Updated repository product",
        unit_price=Decimal("29.95"),
        currency=Currency.GBP,
        stock_quantity=25,
        is_active=False,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(original)
        updated = await repository.update(original.id, replacement)

    assert updated is not None
    assert updated.id == original.id
    assert updated.created_at == original.created_at
    assert updated.sku == replacement.sku
    assert updated.name == replacement.name
    assert updated.description == replacement.description
    assert updated.unit_price == Decimal("29.95")
    assert updated.currency is Currency.GBP
    assert updated.stock_quantity == 25
    assert updated.is_active is False


async def test_update_returns_none_for_unknown_product() -> None:
    replacement = make_product("update-unknown")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        updated = await repository.update(uuid4(), replacement)

    assert updated is None


async def test_adjust_stock_increases_and_decreases_quantity() -> None:
    product = make_product(
        "adjust-stock",
        stock_quantity=10,
    )

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)

        increased = await repository.adjust_stock(product.id, 5)
        decreased = await repository.adjust_stock(product.id, -3)

    assert increased is not None
    assert increased.stock_quantity == 15

    assert decreased is not None
    assert decreased.stock_quantity == 12


async def test_adjust_stock_returns_none_for_unknown_product() -> None:
    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        adjusted = await repository.adjust_stock(uuid4(), 5)

    assert adjusted is None


async def test_adjust_stock_rejects_negative_result() -> None:
    product = make_product(
        "negative-stock",
        stock_quantity=4,
    )

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)

        with pytest.raises(
            ValueError,
            match="stock quantity cannot be negative",
        ):
            await repository.adjust_stock(product.id, -5)

        stored = await repository.get_by_id(product.id)

    assert stored is not None
    assert stored.stock_quantity == 4


async def test_deactivate_marks_product_inactive() -> None:
    product = make_product("deactivate")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)
        deactivated = await repository.deactivate(product.id)

    assert deactivated is not None
    assert deactivated.id == product.id
    assert deactivated.is_active is False


async def test_deactivate_is_idempotent() -> None:
    product = make_product("deactivate-idempotent")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)
        first_result = await repository.deactivate(product.id)
        second_result = await repository.deactivate(product.id)

    assert first_result is not None
    assert second_result is not None
    assert first_result.is_active is False
    assert second_result.is_active is False
    assert first_result == second_result


async def test_deactivated_product_is_excluded_from_active_list() -> None:
    product = make_product("excluded")

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        await repository.create(product)
        await repository.deactivate(product.id)
        active_products = await repository.list_active()

    assert product.id not in {
        active_product.id for active_product in active_products
    }


async def test_list_active_rejects_non_positive_limit() -> None:
    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_active(limit=0)
