from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Currency, OrderStatus


class OrderItemCreate(BaseModel):
    """Product and quantity accepted for one new order line."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    """Data accepted when creating an order."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    customer_id: UUID
    items: tuple[OrderItemCreate, ...] = Field(min_length=1)
    currency: Currency = Currency.USD
    notes: str | None = Field(default=None, max_length=1000)


class OrderNotesUpdate(BaseModel):
    """Mutable order notes accepted by the API."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    notes: str | None = Field(default=None, max_length=1000)


class OrderStatusTransition(BaseModel):
    """Requested governed order-status transition."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    target_status: OrderStatus
    human_approved: bool = False
    reason: str | None = Field(default=None, max_length=1000)


class OrderItemResponse(BaseModel):
    """Stored product snapshot returned for one order line."""

    product_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    currency: Currency
    line_total: Decimal


class OrderResponse(BaseModel):
    """Complete order data returned by the API."""

    id: UUID
    customer_id: UUID
    items: tuple[OrderItemResponse, ...]
    currency: Currency
    status: OrderStatus
    notes: str | None
    total_amount: Decimal
    created_at: datetime
