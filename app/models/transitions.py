from app.governance.audit import GovernanceAuditEntry
from app.governance.models import GovernanceResult
from app.models.common import OrderStatus, PaymentStatus, StrictModel
from app.models.order import Order
from app.models.payment import Payment


class OrderTransitionOutcome(StrictModel):
    """Describes the result of one attempted order status transition."""

    original_order: Order
    order: Order
    previous_status: OrderStatus
    requested_status: OrderStatus
    applied: bool
    governance_result: GovernanceResult
    audit_entry: GovernanceAuditEntry


class PaymentTransitionOutcome(StrictModel):
    """Describes the result of one attempted payment status transition."""

    original_payment: Payment
    payment: Payment
    previous_status: PaymentStatus
    requested_status: PaymentStatus
    applied: bool
    governance_result: GovernanceResult
    audit_entry: GovernanceAuditEntry
