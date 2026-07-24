from decimal import Decimal
from uuid import uuid4

import pytest

from app.database.init_db import init_database
from app.database.session import AsyncSessionFactory
from app.governance import GovernanceDecision
from app.models import (
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
)
from app.repositories import GovernanceAuditRepository
from app.services import (
    StateTransitionService,
    is_order_transition_allowed,
    is_payment_transition_allowed,
)


@pytest.fixture(autouse=True)
async def initialize_transition_database() -> None:
    await init_database()


def make_order(
    *,
    status: OrderStatus = OrderStatus.DRAFT,
    unit_price: Decimal = Decimal("40.00"),
) -> Order:
    item = OrderItem(
        product_id=uuid4(),
        sku="TRANSITION-001",
        product_name="Transition Product",
        quantity=1,
        unit_price=unit_price,
    )

    return Order(
        customer_id=uuid4(),
        items=(item,),
        status=status,
    )


def make_payment(
    *,
    status: PaymentStatus = PaymentStatus.PENDING,
    amount: Decimal = Decimal("40.00"),
) -> Payment:
    return Payment(
        order_id=uuid4(),
        amount=amount,
        status=status,
    )


def test_order_transition_graph_accepts_legal_transition() -> None:
    assert is_order_transition_allowed(
        OrderStatus.DRAFT,
        OrderStatus.PENDING_APPROVAL,
    )


def test_payment_transition_graph_rejects_illegal_transition() -> None:
    assert not is_payment_transition_allowed(
        PaymentStatus.PENDING,
        PaymentStatus.REFUNDED,
    )


async def test_legal_order_transition_is_applied_and_audited() -> None:
    order = make_order()

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_order(
            order,
            OrderStatus.PENDING_APPROVAL,
        )

        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_id(outcome.audit_entry.id)

    assert outcome.applied is True
    assert outcome.order.status is OrderStatus.PENDING_APPROVAL
    assert outcome.original_order.status is OrderStatus.DRAFT
    assert outcome.governance_result.decision is GovernanceDecision.ALLOW
    assert stored is not None
    assert stored.decision is GovernanceDecision.ALLOW


async def test_illegal_order_transition_is_denied_and_audited() -> None:
    order = make_order()

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_order(
            order,
            OrderStatus.COMPLETED,
        )

        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_id(outcome.audit_entry.id)

    assert outcome.applied is False
    assert outcome.order.status is OrderStatus.DRAFT
    assert outcome.governance_result.decision is GovernanceDecision.DENY
    assert "not permitted" in outcome.governance_result.reasons[0]
    assert stored is not None
    assert stored.decision is GovernanceDecision.DENY


async def test_order_transition_requires_approval_above_budget() -> None:
    order = make_order(unit_price=Decimal("250.00"))

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_order(
            order,
            OrderStatus.PENDING_APPROVAL,
        )

    assert outcome.applied is False
    assert outcome.order.status is OrderStatus.DRAFT
    assert outcome.governance_result.decision is GovernanceDecision.REQUIRE_APPROVAL
    assert outcome.governance_result.requires_human is True


async def test_approved_order_transition_is_applied() -> None:
    order = make_order(unit_price=Decimal("250.00"))

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_order(
            order,
            OrderStatus.PENDING_APPROVAL,
            human_approved=True,
        )

    assert outcome.applied is True
    assert outcome.order.status is OrderStatus.PENDING_APPROVAL
    assert outcome.governance_result.decision is GovernanceDecision.ALLOW


async def test_legal_payment_state_transition_is_applied() -> None:
    payment = make_payment()

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_payment(
            payment,
            PaymentStatus.AUTHORIZED,
        )

    assert outcome.applied is True
    assert outcome.payment.status is PaymentStatus.AUTHORIZED
    assert outcome.original_payment.status is PaymentStatus.PENDING
    assert outcome.governance_result.decision is GovernanceDecision.ALLOW


async def test_illegal_payment_transition_is_denied_and_audited() -> None:
    payment = make_payment()

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_payment(
            payment,
            PaymentStatus.REFUNDED,
        )

        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_id(outcome.audit_entry.id)

    assert outcome.applied is False
    assert outcome.payment.status is PaymentStatus.PENDING
    assert outcome.governance_result.decision is GovernanceDecision.DENY
    assert stored is not None
    assert stored.decision is GovernanceDecision.DENY


async def test_payment_transition_requires_budget_approval() -> None:
    payment = make_payment(amount=Decimal("250.00"))

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_payment(
            payment,
            PaymentStatus.AUTHORIZED,
        )

    assert outcome.applied is False
    assert outcome.payment.status is PaymentStatus.PENDING
    assert outcome.governance_result.decision is GovernanceDecision.REQUIRE_APPROVAL


async def test_terminal_order_state_cannot_transition() -> None:
    order = make_order(status=OrderStatus.COMPLETED)

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_order(
            order,
            OrderStatus.CANCELLED,
            human_approved=True,
        )

    assert outcome.applied is False
    assert outcome.order.status is OrderStatus.COMPLETED
    assert outcome.governance_result.decision is GovernanceDecision.DENY


async def test_captured_payment_can_transition_to_refunded() -> None:
    payment = make_payment(status=PaymentStatus.CAPTURED)

    async with AsyncSessionFactory() as session:
        service = StateTransitionService(session)
        outcome = await service.transition_payment(
            payment,
            PaymentStatus.REFUNDED,
        )

    assert outcome.applied is True
    assert outcome.payment.status is PaymentStatus.REFUNDED
