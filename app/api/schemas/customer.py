from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    """Data accepted when creating a customer."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
    )


class CustomerUpdate(BaseModel):
    """Mutable customer data accepted by the API."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
    )


class CustomerResponse(BaseModel):
    """Customer data returned by the API."""

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    is_active: bool
    created_at: datetime
