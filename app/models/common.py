from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base model with strict and immutable domain behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Currency(StrEnum):
    """Supported currencies for local domain validation."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class OrderStatus(StrEnum):
    """Lifecycle states supported by an order."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    """Lifecycle states supported by a payment."""

    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


MONEY_QUANTUM = Decimal("0.01")