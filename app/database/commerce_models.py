from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CustomerRecord(Base):
    """Stores one customer in the local commerce database."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )


class ProductRecord(Base):
    """Stores one sellable product and its current stock quantity."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "unit_price > 0",
            name="ck_products_unit_price_positive",
        ),
        CheckConstraint(
            "stock_quantity >= 0",
            name="ck_products_stock_quantity_non_negative",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )


class OrderRecord(Base):
    """Stores one customer order."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    customer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )


class OrderItemRecord(Base):
    """Stores one product snapshot inside an order."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_order_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price > 0",
            name="ck_order_items_unit_price_positive",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )


class PaymentRecord(Base):
    """Stores one local payment record."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_payments_amount_positive",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
