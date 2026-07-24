from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import EmailStr, Field

from app.models.common import StrictModel


class Customer(StrictModel):
    """Represents a customer in the local commerce domain."""

    id: UUID = Field(default_factory=uuid4)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
