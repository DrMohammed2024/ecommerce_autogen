from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.schemas.customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
)

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def to_response(customer: Customer) -> CustomerResponse:
    """Convert a customer domain model into an API response."""

    return CustomerResponse(
        id=customer.id,
        full_name=customer.full_name,
        email=customer.email,
        phone=customer.phone,
        is_active=customer.is_active,
        created_at=customer.created_at,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    payload: CustomerCreate,
    session: SessionDependency,
) -> CustomerResponse:
    """Create and persist a customer."""

    repository = CustomerRepository(session)

    existing_customer = await repository.get_by_email(payload.email)
    if existing_customer is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this email already exists.",
        )

    customer = Customer(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
    )
    created_customer = await repository.create(customer)

    return to_response(created_customer)


@router.get(
    "",
    response_model=list[CustomerResponse],
)
async def list_customers(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CustomerResponse]:
    """Return active customers in stable creation order."""

    repository = CustomerRepository(session)
    customers = await repository.list_active(limit=limit)

    return [to_response(customer) for customer in customers]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def get_customer(
    customer_id: UUID,
    session: SessionDependency,
) -> CustomerResponse:
    """Return one customer by identifier."""

    repository = CustomerRepository(session)
    customer = await repository.get_by_id(customer_id)

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return to_response(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    session: SessionDependency,
) -> CustomerResponse:
    """Update mutable customer fields."""

    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided.",
        )

    if "full_name" in payload.model_fields_set and payload.full_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="full_name cannot be null.",
        )

    if "email" in payload.model_fields_set and payload.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email cannot be null.",
        )

    repository = CustomerRepository(session)
    customer = await repository.get_by_id(customer_id)

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    if payload.email is not None and payload.email != customer.email:
        email_owner = await repository.get_by_email(payload.email)
        if email_owner is not None and email_owner.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this email already exists.",
            )

    updated_model = Customer(
        id=customer.id,
        full_name=(payload.full_name if payload.full_name is not None else customer.full_name),
        email=(payload.email if payload.email is not None else customer.email),
        phone=(payload.phone if "phone" in payload.model_fields_set else customer.phone),
        is_active=customer.is_active,
        created_at=customer.created_at,
    )

    updated_customer = await repository.update(customer_id, updated_model)

    if updated_customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return to_response(updated_customer)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_customer(
    customer_id: UUID,
    session: SessionDependency,
) -> Response:
    """Deactivate a customer without deleting its stored record."""

    repository = CustomerRepository(session)
    customer = await repository.deactivate(customer_id)

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
