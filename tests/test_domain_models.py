from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import (
    Currency,
    Customer,
    Order,
    OrderItem,
    Payment,
    PaymentStatus,
    Product,
)


def test_customer_accepts_valid_data() -> None:
    customer = Customer(
        full_name="Ahmed Ali",
        email="ahmed@example.com",
    )

    assert customer.full_name == "Ahmed Ali"
    assert customer.email == "ahmed@example.com"
    assert customer.is_active is True


def test_customer_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        Customer(
            full_name="Ahmed Ali",
            email="not-an-email",
        )


def test_product_normalizes_price() -> None:
    product = Product(
        sku="SKU-001",
        name="Test Product",
        unit_price=Decimal("10.999"),
        stock_quantity=3,
    )

    assert product.unit_price == Decimal("11.00")


def test_product_rejects_negative_stock() -> None:
    with pytest.raises(ValidationError):
        Product(
            sku="SKU-002",
            name="Invalid Product",
            unit_price=Decimal("10.00"),
            stock_quantity=-1,
        )


def test_order_item_calculates_line_total() -> None:
    product = Product(
        sku="SKU-003",
        name="Order Product",
        unit_price=Decimal("15.25"),
        stock_quantity=10,
    )

    item = OrderItem(
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        quantity=3,
        unit_price=product.unit_price,
        currency=product.currency,
    )

    assert item.line_total == Decimal("45.75")


def test_order_calculates_total_amount() -> None:
    customer = Customer(
        full_name="Sara Omar",
        email="sara@example.com",
    )
    first_product = Product(
        sku="SKU-004",
        name="First Product",
        unit_price=Decimal("20.00"),
        stock_quantity=10,
    )
    second_product = Product(
        sku="SKU-005",
        name="Second Product",
        unit_price=Decimal("5.50"),
        stock_quantity=10,
    )

    first_item = OrderItem(
        product_id=first_product.id,
        sku=first_product.sku,
        product_name=first_product.name,
        quantity=2,
        unit_price=first_product.unit_price,
    )
    second_item = OrderItem(
        product_id=second_product.id,
        sku=second_product.sku,
        product_name=second_product.name,
        quantity=1,
        unit_price=second_product.unit_price,
    )

    order = Order(
        customer_id=customer.id,
        items=(first_item, second_item),
    )

    assert order.total_amount == Decimal("45.50")


def test_order_rejects_mixed_currencies() -> None:
    customer = Customer(
        full_name="Mona Said",
        email="mona@example.com",
    )
    product = Product(
        sku="SKU-006",
        name="Euro Product",
        unit_price=Decimal("10.00"),
        currency=Currency.EUR,
        stock_quantity=4,
    )
    item = OrderItem(
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        quantity=1,
        unit_price=product.unit_price,
        currency=Currency.EUR,
    )

    with pytest.raises(ValidationError):
        Order(
            customer_id=customer.id,
            items=(item,),
            currency=Currency.USD,
        )


def test_payment_normalizes_amount() -> None:
    customer = Customer(
        full_name="Yousef Adel",
        email="yousef@example.com",
    )
    product = Product(
        sku="SKU-007",
        name="Payment Product",
        unit_price=Decimal("30.00"),
        stock_quantity=2,
    )
    item = OrderItem(
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        quantity=1,
        unit_price=product.unit_price,
    )
    order = Order(
        customer_id=customer.id,
        items=(item,),
    )

    payment = Payment(
        order_id=order.id,
        amount=Decimal("30.005"),
        status=PaymentStatus.PENDING,
    )

    assert payment.amount == Decimal("30.00")
    assert payment.status is PaymentStatus.PENDING


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Customer(
            full_name="Unknown Field",
            email="valid@example.com",
            unsupported_field="value",
        )