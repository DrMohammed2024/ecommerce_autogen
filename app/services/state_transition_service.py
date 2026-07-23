from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.models import (
    ActionType,
    GovernanceDecision,
    GovernancePolicy,
    GovernanceRequest,
    GovernanceResult,
)
from app.models.common import OrderStatus, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.transitions import (
    OrderTransitionOutcome,
    PaymentTransitionOutcome,
)
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
)
from app.services.governance_service import GovernanceService

ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset(
        {
            OrderStatus.PENDING_APPROVAL,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.PENDING_APPROVAL: frozenset(
        {
            OrderStatus.APPROVED,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.APPROVED: frozenset(
        {
            OrderStatus.PROCESSING,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.PROCESSING: frozenset(
        {
            OrderStatus.COMPLETED,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


PAYMENT_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {
            PaymentStatus.AUTHORIZED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        }
    ),
    PaymentStatus.AUTHORIZED: frozenset(
        {
            PaymentStatus.CAPTURED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        }
    ),
    PaymentStatus.CAPTURED: frozenset(
        {
            PaymentStatus.REFUNDED,
        }
    ),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
    PaymentStatus.CANCELLED: frozenset(),
}


class StateTransitionService:
    """Validates, governs, audits, and applies local state transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._governance_service = GovernanceService(session)
        self._audit_repository = GovernanceAuditRepository(session)

    async def transition_order(
        self,
        order: Order,
        target_status: OrderStatus,
        *,
        human_approved: bool = False,
        policy: GovernancePolicy | None = None,
        reason: str | None = None,
    ) -> OrderTransitionOutcome:
        """Attempt an order transition without mutating the original order."""

        request = GovernanceRequest(
            action=ActionType.ORDER_STATUS_TRANSITION,
            amount=order.total_amount,
            currency=order.currency,
            human_approved=human_approved,
            reason=reason,
        )

        if target_status not in ORDER_TRANSITIONS[order.status]:
            result = self._illegal_transition_result(
                request=request,
                entity_name="Order",
                current_status=order.status.value,
                target_status=target_status.value,
            )
            audit_entry = await self._audit_repository.add(request, result)

            return OrderTransitionOutcome(
                original_order=order,
                order=order,
                previous_status=order.status,
                requested_status=target_status,
                applied=False,
                governance_result=result,
                audit_entry=audit_entry,
            )

        evaluation = await self._governance_service.evaluate_and_record(
            request,
            policy,
        )

        transitioned_order = order
        applied = evaluation.result.decision is GovernanceDecision.ALLOW

        if applied:
            transitioned_order = order.model_copy(
                update={"status": target_status}
            )

        return OrderTransitionOutcome(
            original_order=order,
            order=transitioned_order,
            previous_status=order.status,
            requested_status=target_status,
            applied=applied,
            governance_result=evaluation.result,
            audit_entry=evaluation.audit_entry,
        )

    async def transition_payment(
        self,
        payment: Payment,
        target_status: PaymentStatus,
        *,
        human_approved: bool = False,
        policy: GovernancePolicy | None = None,
        reason: str | None = None,
    ) -> PaymentTransitionOutcome:
        """Attempt a payment-state transition without executing a payment."""

        request = GovernanceRequest(
            action=ActionType.PAYMENT_STATUS_TRANSITION,
            amount=payment.amount,
            currency=payment.currency,
            human_approved=human_approved,
            reason=reason,
        )

        if target_status not in PAYMENT_TRANSITIONS[payment.status]:
            result = self._illegal_transition_result(
                request=request,
                entity_name="Payment",
                current_status=payment.status.value,
                target_status=target_status.value,
            )
            audit_entry = await self._audit_repository.add(request, result)

            return PaymentTransitionOutcome(
                original_payment=payment,
                payment=payment,
                previous_status=payment.status,
                requested_status=target_status,
                applied=False,
                governance_result=result,
                audit_entry=audit_entry,
            )

        evaluation = await self._governance_service.evaluate_and_record(
            request,
            policy,
        )

        transitioned_payment = payment
        applied = evaluation.result.decision is GovernanceDecision.ALLOW

        if applied:
            transitioned_payment = payment.model_copy(
                update={"status": target_status}
            )

        return PaymentTransitionOutcome(
            original_payment=payment,
            payment=transitioned_payment,
            previous_status=payment.status,
            requested_status=target_status,
            applied=applied,
            governance_result=evaluation.result,
            audit_entry=evaluation.audit_entry,
        )

    @staticmethod
    def _illegal_transition_result(
        *,
        request: GovernanceRequest,
        entity_name: str,
        current_status: str,
        target_status: str,
    ) -> GovernanceResult:
        """Create a denied result for a transition outside the state graph."""

        return GovernanceResult(
            request_id=request.id,
            decision=GovernanceDecision.DENY,
            reasons=(
                f"{entity_name} transition from "
                f"'{current_status}' to '{target_status}' is not permitted.",
            ),
            requires_human=False,
        )


def is_order_transition_allowed(
    current_status: OrderStatus,
    target_status: OrderStatus,
) -> bool:
    """Return whether an order transition exists in the state graph."""

    return target_status in ORDER_TRANSITIONS[current_status]


def is_payment_transition_allowed(
    current_status: PaymentStatus,
    target_status: PaymentStatus,
) -> bool:
    """Return whether a payment transition exists in the state graph."""

    return target_status in PAYMENT_TRANSITIONS[current_status]


def transition_amount_is_positive(amount: Decimal) -> bool:
    """Return whether an amount can participate in policy evaluation."""

    return amount > Decimal("0.00")