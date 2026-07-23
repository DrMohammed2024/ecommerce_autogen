from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.models.common import (
    MONEY_QUANTUM,
    Currency,
    PaymentStatus,
    StrictModel,
)


class Payment(StrictModel):
    """Represents a local payment record without performing a real transaction."""

    id: UUID = Field(default_factory=uuid4)
    order_id: UUID
    amount: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD
    status: PaymentStatus = PaymentStatus.PENDING
    provider_reference: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("amount")
    @classmethod
    def normalize_amount(cls, value: Decimal) -> Decimal:
        """Normalize the payment amount to two decimal places."""

        return value.quantize(MONEY_QUANTUM)