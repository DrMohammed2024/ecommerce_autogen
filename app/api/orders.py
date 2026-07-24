from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.schemas.order import (
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
)
from app.models.common import OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def to_response(order: Order) -> OrderResponse:
    """Convert an order domain model into an API response."""

    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        items=tuple(
            OrderItemResponse(
                product_id=item.product_id,
                sku=item.sku,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                currency=item.currency,
                line_total=item.line_total,
            )
            for item in order.items
        ),
        currency=order.currency,
        status=order.status,
        notes=order.notes,
        total_amount=order.total_amount,
        created_at=order.created_at,
    )


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    payload: OrderCreate,
    session: SessionDependency,
) -> OrderResponse:
    """Create an order and decrement stock in one database transaction."""

    customer_repository = CustomerRepository(session)
    product_repository = ProductRepository(session)
    order_repository = OrderRepository(session)

    try:
        customer = await customer_repository.get_by_id(payload.customer_id)

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

        if not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer is inactive.",
            )

        product_ids = [item.product_id for item in payload.items]

        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate products are not allowed in one order.",
            )

        resolved_items: list[tuple[Product, int]] = []

        for requested_item in payload.items:
            product = await product_repository.get_by_id(requested_item.product_id)

            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(f"Product {requested_item.product_id} was not found."),
                )

            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product {product.id} is inactive.",
                )

            if product.currency is not payload.currency:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(f"Product {product.id} currency does not match the order currency."),
                )

            if product.stock_quantity < requested_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for product {product.id}.",
                )

            resolved_items.append(
                (
                    product,
                    requested_item.quantity,
                )
            )

        order = Order(
            customer_id=payload.customer_id,
            items=tuple(
                OrderItem(
                    product_id=product.id,
                    sku=product.sku,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.unit_price,
                    currency=product.currency,
                )
                for product, quantity in resolved_items
            ),
            currency=payload.currency,
            status=OrderStatus.DRAFT,
            notes=payload.notes,
        )

        for product, quantity in resolved_items:
            await product_repository.adjust_stock(
                product.id,
                -quantity,
                commit=False,
            )

        created = await order_repository.create(
            order,
            commit=False,
        )

        await session.commit()

        return to_response(created)

    except HTTPException:
        await session.rollback()
        raise
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        await session.rollback()
        raise


@router.get(
    "",
    response_model=list[OrderResponse],
)
async def list_orders(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[OrderResponse]:
    """Return orders in stable creation order."""

    repository = OrderRepository(session)
    orders = await repository.list_all(limit=limit)

    return [to_response(order) for order in orders]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
async def get_order(
    order_id: UUID,
    session: SessionDependency,
) -> OrderResponse:
    """Return one order by identifier."""

    repository = OrderRepository(session)
    order = await repository.get_by_id(order_id)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    return to_response(order)
