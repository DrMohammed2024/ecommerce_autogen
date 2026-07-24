from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionFactory, init_database
from app.database.commerce_models import (
    OrderItemRecord,
    OrderRecord,
    PaymentRecord,
)
from app.models.common import (
    Currency,
    OrderStatus,
    PaymentStatus,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.repositories import OrderRepository, PaymentRepository


@pytest.fixture(autouse=True)
async def initialize_payment_repository_database() -> AsyncIterator[None]:
    """Initialize and clean payment-related tables around every test."""

    await init_database()

    async with AsyncSessionFactory() as session:
        await session.execute(delete(PaymentRecord))
        await session.execute(delete(OrderItemRecord))
        await session.execute(delete(OrderRecord))
        await session.commit()

    yield

    async with AsyncSessionFactory() as session:
        await session.execute(delete(PaymentRecord))
        await session.execute(delete(OrderItemRecord))
        await session.execute(delete(OrderRecord))
        await session.commit()


def make_order(
    *,
    created_at: datetime | None = None,
) -> Order:
    """Create a valid order domain object for repository tests."""

    item = OrderItem(
        product_id=uuid4(),
        sku=f"PAYMENT-ORDER-{uuid4().hex[:8]}",
        product_name="Payment Test Product",
        quantity=1,
        unit_price=Decimal("100.00"),
        currency=Currency.USD,
    )

    return Order(
        customer_id=uuid4(),
        items=(item,),
        currency=Currency.USD,
        status=OrderStatus.DRAFT,
        created_at=created_at or datetime.now(UTC),
    )


def make_payment(
    order_id: UUID,
    *,
    amount: Decimal = Decimal("100.00"),
    currency: Currency = Currency.USD,
    status: PaymentStatus = PaymentStatus.PENDING,
    provider_reference: str | None = None,
    created_at: datetime | None = None,
) -> Payment:
    """Create a valid payment domain object for repository tests."""

    return Payment(
        order_id=order_id,
        amount=amount,
        currency=currency,
        status=status,
        provider_reference=provider_reference,
        created_at=created_at or datetime.now(UTC),
    )


async def persist_order(order: Order) -> None:
    """Persist an order required by a payment foreign key."""

    async with AsyncSessionFactory() as session:
        repository = OrderRepository(session)
        await repository.create(order)


async def test_create_persists_payment() -> None:
    order = make_order()
    await persist_order(order)

    payment = make_payment(
        order.id,
        amount=Decimal("75.50"),
        provider_reference="provider-001",
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        created = await repository.create(payment)

    assert created.id == payment.id
    assert created.order_id == order.id
    assert created.amount == Decimal("75.50")
    assert created.currency is Currency.USD
    assert created.status is PaymentStatus.PENDING
    assert created.provider_reference == "provider-001"


async def test_get_by_id_returns_payment() -> None:
    order = make_order()
    await persist_order(order)

    payment = make_payment(order.id)

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(payment)

        stored = await repository.get_by_id(payment.id)

    assert stored is not None
    assert stored.id == payment.id
    assert stored.order_id == order.id
    assert stored.amount == payment.amount


async def test_get_by_id_returns_none_for_unknown_payment() -> None:
    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        stored = await repository.get_by_id(uuid4())

    assert stored is None


async def test_list_by_order_id_returns_only_matching_payments() -> None:
    first_order = make_order()
    second_order = make_order()

    await persist_order(first_order)
    await persist_order(second_order)

    first = make_payment(first_order.id)
    second = make_payment(
        first_order.id,
        amount=Decimal("50.00"),
    )
    unrelated = make_payment(second_order.id)

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(first)
        await repository.create(second)
        await repository.create(unrelated)

        stored = await repository.list_by_order_id(first_order.id)

    assert {payment.id for payment in stored} == {
        first.id,
        second.id,
    }
    assert all(payment.order_id == first_order.id for payment in stored)


async def test_list_by_order_id_uses_stable_creation_order() -> None:
    order = make_order()
    await persist_order(order)

    base_time = datetime(2026, 1, 1, tzinfo=UTC)

    first = make_payment(
        order.id,
        created_at=base_time,
    )
    second = make_payment(
        order.id,
        created_at=base_time + timedelta(minutes=1),
    )
    third = make_payment(
        order.id,
        created_at=base_time + timedelta(minutes=2),
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(third)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_order_id(order.id)

    assert [payment.id for payment in stored] == [
        first.id,
        second.id,
        third.id,
    ]


async def test_list_by_order_id_applies_limit() -> None:
    order = make_order()
    await persist_order(order)

    base_time = datetime(2026, 2, 1, tzinfo=UTC)

    first = make_payment(
        order.id,
        created_at=base_time,
    )
    second = make_payment(
        order.id,
        created_at=base_time + timedelta(minutes=1),
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_order_id(
            order.id,
            limit=1,
        )

    assert len(stored) == 1
    assert stored[0].id == first.id


async def test_list_by_status_returns_only_matching_payments() -> None:
    order = make_order()
    await persist_order(order)

    first_pending = make_payment(
        order.id,
        status=PaymentStatus.PENDING,
    )
    second_pending = make_payment(
        order.id,
        status=PaymentStatus.PENDING,
    )
    failed = make_payment(
        order.id,
        status=PaymentStatus.FAILED,
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(first_pending)
        await repository.create(second_pending)
        await repository.create(failed)

        stored = await repository.list_by_status(PaymentStatus.PENDING)

    assert {payment.id for payment in stored} == {
        first_pending.id,
        second_pending.id,
    }
    assert all(payment.status is PaymentStatus.PENDING for payment in stored)


async def test_list_by_status_applies_limit() -> None:
    order = make_order()
    await persist_order(order)

    base_time = datetime(2026, 3, 1, tzinfo=UTC)

    first = make_payment(
        order.id,
        status=PaymentStatus.PENDING,
        created_at=base_time,
    )
    second = make_payment(
        order.id,
        status=PaymentStatus.PENDING,
        created_at=base_time + timedelta(minutes=1),
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(first)
        await repository.create(second)

        stored = await repository.list_by_status(
            PaymentStatus.PENDING,
            limit=1,
        )

    assert len(stored) == 1
    assert stored[0].id == first.id


async def test_update_provider_reference_changes_only_reference() -> None:
    order = make_order()
    await persist_order(order)

    payment = make_payment(
        order.id,
        provider_reference=None,
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(payment)

        updated = await repository.update_provider_reference(
            payment.id,
            "provider-updated-001",
        )

    assert updated is not None
    assert updated.id == payment.id
    assert updated.order_id == payment.order_id
    assert updated.amount == payment.amount
    assert updated.currency is payment.currency
    assert updated.status is payment.status
    assert updated.provider_reference == "provider-updated-001"


async def test_update_provider_reference_can_clear_reference() -> None:
    order = make_order()
    await persist_order(order)

    payment = make_payment(
        order.id,
        provider_reference="temporary-reference",
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(payment)

        updated = await repository.update_provider_reference(
            payment.id,
            None,
        )

    assert updated is not None
    assert updated.provider_reference is None


async def test_update_provider_reference_returns_none_for_unknown_payment() -> None:
    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        updated = await repository.update_provider_reference(
            uuid4(),
            "unknown-reference",
        )

    assert updated is None


@pytest.mark.parametrize("limit", [0, -1])
async def test_list_by_order_id_rejects_non_positive_limit(
    limit: int,
) -> None:
    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_by_order_id(
                uuid4(),
                limit=limit,
            )


@pytest.mark.parametrize("limit", [0, -1])
async def test_list_by_status_rejects_non_positive_limit(
    limit: int,
) -> None:
    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_by_status(
                PaymentStatus.PENDING,
                limit=limit,
            )


async def test_loaded_created_at_is_timezone_aware_utc() -> None:
    order = make_order()
    await persist_order(order)

    payment = make_payment(
        order.id,
        created_at=datetime(2026, 4, 1, 12, 30, tzinfo=UTC),
    )

    async with AsyncSessionFactory() as session:
        repository = PaymentRepository(session)
        await repository.create(payment)

        stored = await repository.get_by_id(payment.id)

    assert stored is not None
    assert stored.created_at.tzinfo is not None
    assert stored.created_at.utcoffset() == timedelta(0)
