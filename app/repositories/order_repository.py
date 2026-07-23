from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.commerce_models import OrderItemRecord, OrderRecord
from app.models.common import Currency, OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem


class OrderRepository:
    """Persists and retrieves orders and their item snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, order: Order) -> Order:
        """Persist an order and all its items in one transaction."""

        order_record = OrderRecord(
            id=str(order.id),
            customer_id=str(order.customer_id),
            currency=order.currency.value,
            status=order.status.value,
            notes=order.notes,
            created_at=order.created_at,
        )

        item_records = [
            OrderItemRecord(
                order_id=str(order.id),
                product_id=str(item.product_id),
                sku=item.sku,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                currency=item.currency.value,
            )
            for item in order.items
        ]

        self._session.add(order_record)
        self._session.add_all(item_records)

        await self._session.commit()
        await self._session.refresh(order_record)

        return await self._to_domain(order_record)

    async def get_by_id(
        self,
        order_id: UUID,
    ) -> Order | None:
        """Return one order with all its items, or None when not found."""

        record = await self._session.get(
            OrderRecord,
            str(order_id),
        )

        if record is None:
            return None

        return await self._to_domain(record)

    async def list_by_customer(
        self,
        customer_id: UUID,
        limit: int = 100,
    ) -> tuple[Order, ...]:
        """Return orders for one customer in stable creation order."""

        self._validate_limit(limit)

        statement = (
            select(OrderRecord)
            .where(OrderRecord.customer_id == str(customer_id))
            .order_by(
                OrderRecord.created_at.asc(),
                OrderRecord.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)
        records: Sequence[OrderRecord] = result.scalars().all()

        return tuple(
            [await self._to_domain(record) for record in records]
        )

    async def list_by_status(
        self,
        status: OrderStatus,
        limit: int = 100,
    ) -> tuple[Order, ...]:
        """Return orders having one status in stable creation order."""

        self._validate_limit(limit)

        statement = (
            select(OrderRecord)
            .where(OrderRecord.status == status.value)
            .order_by(
                OrderRecord.created_at.asc(),
                OrderRecord.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)
        records: Sequence[OrderRecord] = result.scalars().all()

        return tuple(
            [await self._to_domain(record) for record in records]
        )

    async def update_notes(
        self,
        order_id: UUID,
        notes: str | None,
    ) -> Order | None:
        """Update order notes without changing identity, items, or status."""

        record = await self._session.get(
            OrderRecord,
            str(order_id),
        )

        if record is None:
            return None

        record.notes = notes

        await self._session.commit()
        await self._session.refresh(record)

        return await self._to_domain(record)

    async def _to_domain(
        self,
        record: OrderRecord,
    ) -> Order:
        """Convert one order record and its items to a domain model."""

        statement = (
            select(OrderItemRecord)
            .where(OrderItemRecord.order_id == record.id)
            .order_by(OrderItemRecord.id.asc())
        )

        result = await self._session.execute(statement)
        item_records: Sequence[OrderItemRecord] = result.scalars().all()

        items = tuple(
            OrderItem(
                product_id=UUID(item_record.product_id),
                sku=item_record.sku,
                product_name=item_record.product_name,
                quantity=item_record.quantity,
                unit_price=item_record.unit_price,
                currency=Currency(item_record.currency),
            )
            for item_record in item_records
        )

        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return Order(
            id=UUID(record.id),
            customer_id=UUID(record.customer_id),
            items=items,
            currency=Currency(record.currency),
            status=OrderStatus(record.status),
            notes=record.notes,
            created_at=created_at,
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        """Reject non-positive query limits."""

        if limit < 1:
            raise ValueError("limit must be greater than zero.")
