from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.commerce_models import CustomerRecord
from app.models.customer import Customer


class CustomerRepository:
    """Persists and retrieves customers from the local database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, customer: Customer) -> Customer:
        """Persist one customer and return the validated domain model."""

        record = CustomerRecord(
            id=str(customer.id),
            full_name=customer.full_name,
            email=str(customer.email),
            phone=customer.phone,
            is_active=customer.is_active,
            created_at=customer.created_at,
        )

        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    async def get_by_id(self, customer_id: UUID) -> Customer | None:
        """Return one customer by identifier, or None when not found."""

        record = await self._session.get(
            CustomerRecord,
            str(customer_id),
        )

        if record is None:
            return None

        return self._to_domain(record)

    async def get_by_email(self, email: EmailStr | str) -> Customer | None:
        """Return one customer by email address, or None when not found."""

        statement = select(CustomerRecord).where(
            CustomerRecord.email == str(email)
        )
        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_domain(record)

    async def list_active(
        self,
        limit: int = 100,
    ) -> tuple[Customer, ...]:
        """Return active customers in stable creation order."""

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        statement = (
            select(CustomerRecord)
            .where(CustomerRecord.is_active.is_(True))
            .order_by(
                CustomerRecord.created_at.asc(),
                CustomerRecord.id.asc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(statement)
        records: Sequence[CustomerRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    async def update(
        self,
        customer_id: UUID,
        customer: Customer,
    ) -> Customer | None:
        """Update mutable customer fields without changing its identity."""

        record = await self._session.get(
            CustomerRecord,
            str(customer_id),
        )

        if record is None:
            return None

        record.full_name = customer.full_name
        record.email = str(customer.email)
        record.phone = customer.phone
        record.is_active = customer.is_active

        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    async def deactivate(
        self,
        customer_id: UUID,
    ) -> Customer | None:
        """Deactivate one customer and return its current domain model."""

        record = await self._session.get(
            CustomerRecord,
            str(customer_id),
        )

        if record is None:
            return None

        if record.is_active:
            record.is_active = False
            await self._session.commit()
            await self._session.refresh(record)

        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: CustomerRecord) -> Customer:
        """Convert a database customer record to a domain model."""

        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return Customer(
            id=UUID(record.id),
            full_name=record.full_name,
            email=record.email,
            phone=record.phone,
            is_active=record.is_active,
            created_at=created_at,
        )



