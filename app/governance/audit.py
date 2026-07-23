from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.governance.models import (
    ActionType,
    GovernanceDecision,
    GovernanceRequest,
    GovernanceResult,
)
from app.models.common import Currency, StrictModel


class GovernanceAuditEntry(StrictModel):
    """Represents a governance audit record returned by the repository."""

    id: UUID
    request_id: UUID
    action: ActionType
    amount: Decimal
    currency: Currency
    human_approved: bool
    decision: GovernanceDecision
    requires_human: bool
    reasons: tuple[str, ...]
    external_target: str | None
    created_at: datetime


class GovernanceEvaluation(StrictModel):
    """Contains both the decision and its persisted audit entry."""

    request: GovernanceRequest
    result: GovernanceResult
    audit_entry: GovernanceAuditEntry