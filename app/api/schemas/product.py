from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import Currency


class ProductCreate(BaseModel):
    """Data accepted when creating a product."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    sku: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD
    stock_quantity: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    """Mutable product data accepted by the API."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    sku: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency: Currency | None = None


class StockAdjustment(BaseModel):
    """Signed product stock adjustment."""

    model_config = ConfigDict(extra="forbid")

    quantity_delta: int

    @field_validator("quantity_delta")
    @classmethod
    def reject_zero_quantity_delta(cls, value: int) -> int:
        """Require a non-zero stock adjustment."""

        if value == 0:
            raise ValueError("quantity_delta must not be zero")
        return value


class ProductResponse(BaseModel):
    """Product data returned by the API."""

    id: UUID
    sku: str
    name: str
    description: str | None
    unit_price: Decimal
    currency: Currency
    stock_quantity: int
    is_active: bool
    created_at: datetime
