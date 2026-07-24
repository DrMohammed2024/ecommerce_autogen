from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockAdjustment,
)
from app.models.product import Product
from app.repositories.product_repository import ProductRepository

router = APIRouter(
    prefix="/products",
    tags=["products"],
)

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def to_response(product: Product) -> ProductResponse:
    """Convert a product domain model into an API response."""

    return ProductResponse(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        unit_price=product.unit_price,
        currency=product.currency,
        stock_quantity=product.stock_quantity,
        is_active=product.is_active,
        created_at=product.created_at,
    )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    session: SessionDependency,
) -> ProductResponse:
    """Create and persist a product."""

    repository = ProductRepository(session)

    existing_product = await repository.get_by_sku(payload.sku)
    if existing_product is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists.",
        )

    product = Product(
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        unit_price=payload.unit_price,
        currency=payload.currency,
        stock_quantity=payload.stock_quantity,
    )
    created_product = await repository.create(product)

    return to_response(created_product)


@router.get(
    "",
    response_model=list[ProductResponse],
)
async def list_products(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ProductResponse]:
    """Return active products in stable creation order."""

    repository = ProductRepository(session)
    products = await repository.list_active(limit=limit)

    return [to_response(product) for product in products]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
async def get_product(
    product_id: UUID,
    session: SessionDependency,
) -> ProductResponse:
    """Return one product by identifier."""

    repository = ProductRepository(session)
    product = await repository.get_by_id(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return to_response(product)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    session: SessionDependency,
) -> ProductResponse:
    """Update mutable product fields."""

    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided.",
        )

    required_fields = {
        "sku": payload.sku,
        "name": payload.name,
        "unit_price": payload.unit_price,
        "currency": payload.currency,
    }

    for field_name, field_value in required_fields.items():
        if field_name in payload.model_fields_set and field_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} cannot be null.",
            )

    repository = ProductRepository(session)
    product = await repository.get_by_id(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    if payload.sku is not None and payload.sku != product.sku:
        sku_owner = await repository.get_by_sku(payload.sku)
        if sku_owner is not None and sku_owner.id != product_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this SKU already exists.",
            )

    updated_model = Product(
        id=product.id,
        sku=payload.sku if payload.sku is not None else product.sku,
        name=payload.name if payload.name is not None else product.name,
        description=(
            payload.description
            if "description" in payload.model_fields_set
            else product.description
        ),
        unit_price=(payload.unit_price if payload.unit_price is not None else product.unit_price),
        currency=(payload.currency if payload.currency is not None else product.currency),
        stock_quantity=product.stock_quantity,
        is_active=product.is_active,
        created_at=product.created_at,
    )

    updated_product = await repository.update(product_id, updated_model)

    if updated_product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return to_response(updated_product)


@router.patch(
    "/{product_id}/stock",
    response_model=ProductResponse,
)
async def adjust_product_stock(
    product_id: UUID,
    payload: StockAdjustment,
    session: SessionDependency,
) -> ProductResponse:
    """Increase or decrease product stock."""

    repository = ProductRepository(session)

    try:
        product = await repository.adjust_stock(
            product_id,
            payload.quantity_delta,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return to_response(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_product(
    product_id: UUID,
    session: SessionDependency,
) -> Response:
    """Deactivate a product without deleting its stored record."""

    repository = ProductRepository(session)
    product = await repository.deactivate(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
