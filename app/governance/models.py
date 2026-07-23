from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.models.common import Currency, StrictModel


class ActionType(StrEnum):
    """Actions that can be evaluated by the governance layer."""

    VIEW_DATA = "view_data"
    CREATE_ORDER = "create_order"
    UPDATE_INVENTORY = "update_inventory"
    ISSUE_PAYMENT = "issue_payment"
    EXTERNAL_API_CALL = "external_api_call"
    SEND_MESSAGE = "send_message"
    DELETE_DATA = "delete_data"
    ORDER_STATUS_TRANSITION = "order_status_transition"
    PAYMENT_STATUS_TRANSITION = "payment_status_transition"


class GovernanceDecision(StrEnum):
    """Possible governance decisions for a requested action."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class GovernancePolicy(StrictModel):
    """Configures local safety and spending restrictions."""

    max_automatic_amount: Decimal = Field(
        default=Decimal("100.00"),
        ge=Decimal("0"),
    )
    max_human_approved_amount: Decimal = Field(
        default=Decimal("1000.00"),
        ge=Decimal("0"),
    )
    block_payments: bool = True
    block_external_actions: bool = True


class GovernanceRequest(StrictModel):
    """Describes an action before it is executed."""

    id: UUID = Field(default_factory=uuid4)
    action: ActionType
    amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
    )
    currency: Currency = Currency.USD
    human_approved: bool = False
    external_target: str | None = Field(
        default=None,
        max_length=500,
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
    )


class GovernanceResult(StrictModel):
    """Represents the final governance decision."""

    request_id: UUID
    decision: GovernanceDecision
    reasons: tuple[str, ...]
    requires_human: bool = False