from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas.order import (
    OrderCreate,
    OrderItemCreate,
    OrderItemResponse,
    OrderNotesUpdate,
    OrderResponse,
    OrderStatusTransition,
)
from app.models.common import Currency, OrderStatus


def test_order_item_create_accepts_valid_data() -> None:
    product_id = uuid4()

    item = OrderItemCreate(
        product_id=product_id,
        quantity=2,
    )

    assert item.product_id == product_id
    assert item.quantity == 2


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_item_create_rejects_non_positive_quantity(
    quantity: int,
) -> None:
    with pytest.raises(ValidationError):
        OrderItemCreate(
            product_id=uuid4(),
            quantity=quantity,
        )


def test_order_create_accepts_valid_data_and_defaults() -> None:
    customer_id = uuid4()
    product_id = uuid4()

    order = OrderCreate(
        customer_id=customer_id,
        items=(
            OrderItemCreate(
                product_id=product_id,
                quantity=3,
            ),
        ),
    )

    assert order.customer_id == customer_id
    assert len(order.items) == 1
    assert order.items[0].product_id == product_id
    assert order.items[0].quantity == 3
    assert order.currency is Currency.USD
    assert order.notes is None


def test_order_create_rejects_empty_items() -> None:
    with pytest.raises(ValidationError):
        OrderCreate(
            customer_id=uuid4(),
            items=(),
        )


def test_order_create_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(
            {
                "customer_id": str(uuid4()),
                "items": [
                    {
                        "product_id": str(uuid4()),
                        "quantity": 1,
                    }
                ],
                "unexpected": "value",
            }
        )


def test_order_notes_update_accepts_null_notes() -> None:
    update = OrderNotesUpdate(notes=None)

    assert update.notes is None


def test_order_status_transition_accepts_governance_data() -> None:
    transition = OrderStatusTransition(
        target_status=OrderStatus.PENDING_APPROVAL,
        human_approved=True,
        reason="Approved by operations",
    )

    assert transition.target_status is OrderStatus.PENDING_APPROVAL
    assert transition.human_approved is True
    assert transition.reason == "Approved by operations"


def test_order_response_accepts_complete_order_data() -> None:
    order_id = uuid4()
    customer_id = uuid4()
    product_id = uuid4()
    created_at = datetime(2026, 4, 1, 12, 30, tzinfo=UTC)

    response = OrderResponse(
        id=order_id,
        customer_id=customer_id,
        items=(
            OrderItemResponse(
                product_id=product_id,
                sku="SKU-001",
                product_name="Test Product",
                quantity=2,
                unit_price=Decimal("10.50"),
                currency=Currency.USD,
                line_total=Decimal("21.00"),
            ),
        ),
        currency=Currency.USD,
        status=OrderStatus.DRAFT,
        notes="Test order",
        total_amount=Decimal("21.00"),
        created_at=created_at,
    )

    assert response.id == order_id
    assert response.customer_id == customer_id
    assert response.items[0].product_id == product_id
    assert response.items[0].line_total == Decimal("21.00")
    assert response.total_amount == Decimal("21.00")
    assert response.status is OrderStatus.DRAFT
    assert response.created_at == created_at
