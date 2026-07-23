from decimal import Decimal
from uuid import UUID

from pydantic import Field, computed_field, field_validator

from app.models.common import MONEY_QUANTUM, Currency, StrictModel


class OrderItem(StrictModel):
    """Represents one product line inside an order."""

    product_id: UUID
    sku: str = Field(min_length=1, max_length=64)
    product_name: str = Field(min_length=2, max_length=200)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD

    @field_validator("unit_price")
    @classmethod
    def normalize_unit_price(cls, value: Decimal) -> Decimal:
        """Normalize the item price to two decimal places."""

        return value.quantize(MONEY_QUANTUM)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        """Return the total price for this order line."""

        return (self.unit_price * self.quantity).quantize(MONEY_QUANTUM)