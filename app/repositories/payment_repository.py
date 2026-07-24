from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.commerce_models import PaymentRecord
from app.models.common import Currency, PaymentStatus
from app.models.payment import Payment


class PaymentRepository:
    """Persists and retrieves local payment records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payment: Payment) -> Payment:
        """Persist one local payment record."""

        record = PaymentRecord(
            id=str(payment.id),
            order_id=str(payment.order_id),
            amount=payment.amount,
            currency=payment.currency.value,
            status=payment.status.value,
            provider_reference=payment.provider_reference,
            created_at=payment.created_at,
        )

        self._session.add(record)

        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    async def get_by_id(
        self,
        payment_id: UUID,
    ) -> Payment | None:
        """Return one payment, or None when it does not exist."""

        record = await self._session.get(
            PaymentRecord,
            str(payment_id),
        )

        if record is None:
            return None

        return self._to_domain(record)

    async def list_by_order_id(
        self,
        order_id: UUID,
        limit: int = 100,
    ) -> tuple[Payment, ...]:
        """Return payments for one order in stable creation order."""

        self._validate_limit(limit)

        statement = (
            select(PaymentRecord)
            .where(PaymentRecord.order_id == str(order_id))
            .order_by(
                PaymentRecord.created_at.asc(),
                PaymentRecord.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)
        records: Sequence[PaymentRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    async def list_by_status(
        self,
        status: PaymentStatus,
        limit: int = 100,
    ) -> tuple[Payment, ...]:
        """Return payments having one status in stable creation order."""

        self._validate_limit(limit)

        statement = (
            select(PaymentRecord)
            .where(PaymentRecord.status == status.value)
            .order_by(
                PaymentRecord.created_at.asc(),
                PaymentRecord.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)
        records: Sequence[PaymentRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    async def update_provider_reference(
        self,
        payment_id: UUID,
        provider_reference: str | None,
    ) -> Payment | None:
        """Update only the optional provider reference."""

        record = await self._session.get(
            PaymentRecord,
            str(payment_id),
        )

        if record is None:
            return None

        record.provider_reference = provider_reference

        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: PaymentRecord) -> Payment:
        """Convert one database record into a payment domain model."""

        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return Payment(
            id=UUID(record.id),
            order_id=UUID(record.order_id),
            amount=record.amount,
            currency=Currency(record.currency),
            status=PaymentStatus(record.status),
            provider_reference=record.provider_reference,
            created_at=created_at,
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        """Reject non-positive query limits."""

        if limit < 1:
            raise ValueError("limit must be greater than zero.")
