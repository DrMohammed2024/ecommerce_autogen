from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionFactory, init_database
from app.database.commerce_models import OrderItemRecord, OrderRecord
from app.models.common import Currency, OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories import OrderRepository


@pytest.fixture(autouse=True)
async def initialize_order_repository_database() -> AsyncIterator[None]:
    await init_database()

    async with AsyncSessionFactory() as session:
        await session.execute(delete(OrderItemRecord))
        await session.execute(delete(OrderRecord))
        await session.commit()

    yield

    async with AsyncSessionFactory() as session:
        await session.execute(delete(OrderItemRecord))
        await session.execute(delete(OrderRecord))
        await session.commit()


def make_order(
    *,
    customer_id: UUID | None = None,
    status: OrderStatus = OrderStatus.DRAFT,
    notes: str | None = None,
    created_at: datetime | None = None,
    item_count: int = 1,
) -> Order:
    resolved_customer_id = customer_id or uuid4()
    resolved_created_at = created_at or datetime.now(UTC)

    items = tuple(
        OrderItem(
            product_id=uuid4(),
            sku=f"ORDER-SKU-{index + 1:03d}",
            product_name=f"Order Product {index + 1}",
            quantity=index + 1,
            unit_price=Decimal("25.00") + Decimal(index),
            currency=Currency.USD,
        )
        for index in range(item_count)
    )

    return Order(
        customer_id=resolved_customer_id,
        items=items,
        currency=Currency.USD,
        status=status,
        notes=notes,
        created_at=resolved_created_at,
    )


async def test_create_persists_order() -> None:
    order = make_order(notes="First order")

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        created = await repository.create(order)

    assert created.id == order.id
    assert created.customer_id == order.customer_id
    assert created.currency is Currency.USD
    assert created.status is OrderStatus.DRAFT
    assert created.notes == "First order"
    assert created.total_amount == order.total_amount


async def test_create_persists_all_order_items() -> None:
    order = make_order(item_count=3)

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        created = await repository.create(order)

    assert len(created.items) == 3
    assert sorted(item.sku for item in created.items) == [
        "ORDER-SKU-001",
        "ORDER-SKU-002",
        "ORDER-SKU-003",
    ]
    assert created.total_amount == order.total_amount


async def test_get_by_id_returns_order_with_items() -> None:
    order = make_order(item_count=2)

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(order)

        stored = await repository.get_by_id(order.id)

    assert stored is not None
    assert stored.id == order.id
    assert stored.customer_id == order.customer_id
    assert len(stored.items) == 2
    assert stored.total_amount == order.total_amount


async def test_get_by_id_returns_none_for_unknown_order() -> None:
    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        stored = await repository.get_by_id(uuid4())

    assert stored is None


async def test_list_by_customer_returns_only_matching_orders() -> None:
    matching_customer_id = uuid4()
    other_customer_id = uuid4()

    first = make_order(customer_id=matching_customer_id)
    second = make_order(customer_id=matching_customer_id)
    unrelated = make_order(customer_id=other_customer_id)

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(first)
        await repository.create(second)
        await repository.create(unrelated)

        stored = await repository.list_by_customer(
            matching_customer_id
        )

    assert {order.id for order in stored} == {
        first.id,
        second.id,
    }
    assert all(
        order.customer_id == matching_customer_id
        for order in stored
    )


async def test_list_by_customer_uses_stable_creation_order() -> None:
    customer_id = uuid4()
    base_time = datetime(2026, 1, 1, tzinfo=UTC)

    first = make_order(
        customer_id=customer_id,
        created_at=base_time,
    )
    second = make_order(
        customer_id=customer_id,
        created_at=base_time + timedelta(minutes=1),
    )
    third = make_order(
        customer_id=customer_id,
        created_at=base_time + timedelta(minutes=2),
    )

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(third)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_customer(customer_id)

    assert [order.id for order in stored] == [
        first.id,
        second.id,
        third.id,
    ]


async def test_list_by_customer_applies_limit() -> None:
    customer_id = uuid4()
    base_time = datetime(2026, 2, 1, tzinfo=UTC)

    first = make_order(
        customer_id=customer_id,
        created_at=base_time,
    )
    second = make_order(
        customer_id=customer_id,
        created_at=base_time + timedelta(minutes=1),
    )

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_customer(
            customer_id,
            limit=1,
        )

    assert len(stored) == 1
    assert stored[0].id == first.id


async def test_list_by_status_returns_only_matching_orders() -> None:
    first_draft = make_order(status=OrderStatus.DRAFT)
    second_draft = make_order(status=OrderStatus.DRAFT)
    pending = make_order(status=OrderStatus.PENDING_APPROVAL)

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(first_draft)
        await repository.create(second_draft)
        await repository.create(pending)

        stored = await repository.list_by_status(
            OrderStatus.DRAFT
        )

    assert {order.id for order in stored} == {
        first_draft.id,
        second_draft.id,
    }
    assert all(
        order.status is OrderStatus.DRAFT
        for order in stored
    )


async def test_list_by_status_applies_limit() -> None:
    base_time = datetime(2026, 3, 1, tzinfo=UTC)

    first = make_order(
        status=OrderStatus.DRAFT,
        created_at=base_time,
    )
    second = make_order(
        status=OrderStatus.DRAFT,
        created_at=base_time + timedelta(minutes=1),
    )

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_status(
            OrderStatus.DRAFT,
            limit=1,
        )

    assert len(stored) == 1
    assert stored[0].id == first.id


async def test_update_notes_changes_only_notes() -> None:
    order = make_order(
        notes="Original notes",
        item_count=2,
    )

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(order)

        updated = await repository.update_notes(
            order.id,
            "Updated notes",
        )

    assert updated is not None
    assert updated.id == order.id
    assert updated.customer_id == order.customer_id
    assert updated.status is order.status
    assert updated.notes == "Updated notes"
    assert sorted(
        updated.items,
        key=lambda item: item.sku,
    ) == sorted(
        order.items,
        key=lambda item: item.sku,
    )
    assert updated.created_at == order.created_at


async def test_update_notes_can_clear_notes() -> None:
    order = make_order(notes="Temporary notes")

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(order)

        updated = await repository.update_notes(
            order.id,
            None,
        )

    assert updated is not None
    assert updated.notes is None


async def test_update_notes_returns_none_for_unknown_order() -> None:
    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        updated = await repository.update_notes(
            uuid4(),
            "Unknown order",
        )

    assert updated is None


@pytest.mark.parametrize("limit", [0, -1])
async def test_list_by_customer_rejects_non_positive_limit(
    limit: int,
) -> None:
    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_by_customer(
                uuid4(),
                limit=limit,
            )


@pytest.mark.parametrize("limit", [0, -1])
async def test_list_by_status_rejects_non_positive_limit(
    limit: int,
) -> None:
    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_by_status(
                OrderStatus.DRAFT,
                limit=limit,
            )


async def test_loaded_created_at_is_timezone_aware_utc() -> None:
    order = make_order(
        created_at=datetime(2026, 4, 1, 12, 30, tzinfo=UTC)
    )

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(order)

        stored = await repository.get_by_id(order.id)

    assert stored is not None
    assert stored.created_at.tzinfo is not None
    assert stored.created_at.utcoffset() == timedelta(0)


