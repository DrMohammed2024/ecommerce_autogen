from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GovernanceAuditRecord(Base):
    """Stores one immutable governance decision in the local database."""

    __tablename__ = "governance_audit_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    human_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    requires_human: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reasons_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    external_target: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    @property
    def record_uuid(self) -> UUID:
        """Return the record identifier as UUID."""

        return UUID(self.id)

    @property
    def request_uuid(self) -> UUID:
        """Return the request identifier as UUID."""

        return UUID(self.request_id)
