from decimal import Decimal
from uuid import uuid4

import pytest

from app.api.orders import create_order
from app.api.schemas.order import OrderCreate, OrderItemCreate
from app.database.session import AsyncSessionFactory
from app.models.common import Currency
from app.models.customer import Customer
from app.models.product import Product
from app.repositories.customer_repository import CustomerRepository
from app.repositories.product_repository import ProductRepository


@pytest.mark.asyncio
async def test_create_order_directly_executes_endpoint_body() -> None:
    async with AsyncSessionFactory() as setup_session:
        customer = await CustomerRepository(setup_session).create(
            Customer(
                full_name="Direct Coverage Customer",
                email=f"direct-{uuid4().hex}@example.com",
            )
        )
        product = await ProductRepository(setup_session).create(
            Product(
                sku=f"DIRECT-{uuid4().hex[:8]}",
                name="Direct Coverage Product",
                unit_price=Decimal("10.00"),
                currency=Currency.USD,
                stock_quantity=5,
            )
        )

    payload = OrderCreate(
        customer_id=customer.id,
        items=(
            OrderItemCreate(
                product_id=product.id,
                quantity=2,
            ),
        ),
        currency=Currency.USD,
        notes="Direct endpoint coverage",
    )

    async with AsyncSessionFactory() as session:
        response = await create_order(payload, session)

    assert response.customer_id == customer.id
    assert response.total_amount == Decimal("20.00")

    async with AsyncSessionFactory() as verification_session:
        stored = await ProductRepository(verification_session).get_by_id(product.id)

    assert stored is not None
    assert stored.stock_quantity == 3
