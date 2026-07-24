from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.commerce_models import ProductRecord
from app.models.common import Currency
from app.models.product import Product


class ProductRepository:
    """Persists and retrieves products from the local database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, product: Product) -> Product:
        """Persist one product and return its validated domain model."""

        record = ProductRecord(
            id=str(product.id),
            sku=product.sku,
            name=product.name,
            description=product.description,
            unit_price=product.unit_price,
            currency=product.currency.value,
            stock_quantity=product.stock_quantity,
            is_active=product.is_active,
            created_at=product.created_at,
        )

        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    async def get_by_id(
        self,
        product_id: UUID,
    ) -> Product | None:
        """Return one product by identifier, or None when not found."""

        record = await self._session.get(
            ProductRecord,
            str(product_id),
        )

        if record is None:
            return None

        return self._to_domain(record)

    async def get_by_sku(
        self,
        sku: str,
    ) -> Product | None:
        """Return one product by SKU, or None when not found."""

        statement = select(ProductRecord).where(ProductRecord.sku == sku)
        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_domain(record)

    async def list_active(
        self,
        limit: int = 100,
    ) -> tuple[Product, ...]:
        """Return active products in stable creation order."""

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        statement = (
            select(ProductRecord)
            .where(ProductRecord.is_active.is_(True))
            .order_by(
                ProductRecord.created_at.asc(),
                ProductRecord.id.asc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(statement)
        records: Sequence[ProductRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    async def update(
        self,
        product_id: UUID,
        product: Product,
    ) -> Product | None:
        """Update mutable product fields without changing its identity."""

        record = await self._session.get(
            ProductRecord,
            str(product_id),
        )

        if record is None:
            return None

        record.sku = product.sku
        record.name = product.name
        record.description = product.description
        record.unit_price = product.unit_price
        record.currency = product.currency.value
        record.stock_quantity = product.stock_quantity
        record.is_active = product.is_active

        await self._session.commit()
        await self._session.refresh(record)

        return self._to_domain(record)

    async def adjust_stock(
        self,
        product_id: UUID,
        quantity_delta: int,
        *,
        commit: bool = True,
    ) -> Product | None:
        """Adjust stock by a signed quantity without allowing negative stock."""

        record = await self._session.get(
            ProductRecord,
            str(product_id),
        )

        if record is None:
            return None

        new_quantity = record.stock_quantity + quantity_delta
        if new_quantity < 0:
            raise ValueError("stock quantity cannot be negative.")

        if new_quantity != record.stock_quantity:
            record.stock_quantity = new_quantity
            await self._session.flush()

            if commit:
                await self._session.commit()

            await self._session.refresh(record)

        return self._to_domain(record)

    async def deactivate(
        self,
        product_id: UUID,
    ) -> Product | None:
        """Deactivate one product and return its current domain model."""

        record = await self._session.get(
            ProductRecord,
            str(product_id),
        )

        if record is None:
            return None

        if record.is_active:
            record.is_active = False
            await self._session.commit()
            await self._session.refresh(record)

        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: ProductRecord) -> Product:
        """Convert a database product record to a domain model."""

        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return Product(
            id=UUID(record.id),
            sku=record.sku,
            name=record.name,
            description=record.description,
            unit_price=record.unit_price,
            currency=Currency(record.currency),
            stock_quantity=record.stock_quantity,
            is_active=record.is_active,
            created_at=created_at,
        )
