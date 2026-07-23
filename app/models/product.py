from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.models.common import MONEY_QUANTUM, Currency, StrictModel


class Product(StrictModel):
    """Represents a sellable product."""

    id: UUID = Field(default_factory=uuid4)
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("unit_price")
    @classmethod
    def normalize_unit_price(cls, value: Decimal) -> Decimal:
        """Normalize the product price to two decimal places."""

        return value.quantize(MONEY_QUANTUM)