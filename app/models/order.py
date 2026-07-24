from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import Field, computed_field, model_validator

from app.models.common import MONEY_QUANTUM, Currency, OrderStatus, StrictModel
from app.models.order_item import OrderItem


class Order(StrictModel):
    """Represents a customer order and its line items."""

    id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    items: tuple[OrderItem, ...] = Field(min_length=1)
    currency: Currency = Currency.USD
    status: OrderStatus = OrderStatus.DRAFT
    notes: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_item_currencies(self) -> "Order":
        """Require every order item to use the order currency."""

        invalid_items = [item.sku for item in self.items if item.currency != self.currency]

        if invalid_items:
            joined_skus = ", ".join(invalid_items)
            raise ValueError(f"Order item currencies must match order currency: {joined_skus}")

        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_amount(self) -> Decimal:
        """Return the complete order value."""

        total = sum(
            (item.line_total for item in self.items),
            start=Decimal("0.00"),
        )
        return total.quantize(MONEY_QUANTUM)
