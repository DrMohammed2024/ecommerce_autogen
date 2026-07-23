from decimal import Decimal
from uuid import uuid4

import pytest

from app.database.init_db import init_database
from app.database.session import AsyncSessionFactory
from app.governance import (
    ActionType,
    GovernanceDecision,
    GovernanceRequest,
)
from app.repositories import GovernanceAuditRepository
from app.services import GovernanceService


@pytest.fixture(autouse=True)
async def initialize_audit_database() -> None:
    await init_database()


async def test_service_records_allowed_decision() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("40.00"),
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        evaluation = await service.evaluate_and_record(request)

    assert evaluation.result.decision is GovernanceDecision.ALLOW
    assert evaluation.audit_entry.request_id == request.id
    assert evaluation.audit_entry.amount == Decimal("40.00")


async def test_service_records_denied_payment() -> None:
    request = GovernanceRequest(
        action=ActionType.ISSUE_PAYMENT,
        amount=Decimal("25.00"),
        human_approved=True,
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        evaluation = await service.evaluate_and_record(request)

    assert evaluation.result.decision is GovernanceDecision.DENY
    assert evaluation.audit_entry.decision is GovernanceDecision.DENY
    assert "Payment execution is disabled" in evaluation.audit_entry.reasons[0]


async def test_repository_gets_record_by_id() -> None:
    request = GovernanceRequest(
        action=ActionType.VIEW_DATA,
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        evaluation = await service.evaluate_and_record(request)

        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_id(evaluation.audit_entry.id)

    assert stored is not None
    assert stored.id == evaluation.audit_entry.id
    assert stored.action is ActionType.VIEW_DATA


async def test_repository_gets_record_by_request_id() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("150.00"),
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        await service.evaluate_and_record(request)

        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_request_id(request.id)

    assert stored is not None
    assert stored.request_id == request.id
    assert stored.decision is GovernanceDecision.REQUIRE_APPROVAL


async def test_repository_returns_none_for_unknown_record() -> None:
    async with AsyncSessionFactory() as session:
        repository = GovernanceAuditRepository(session)
        stored = await repository.get_by_id(uuid4())

    assert stored is None


async def test_repository_lists_recent_records() -> None:
    first_request = GovernanceRequest(
        action=ActionType.VIEW_DATA,
    )
    second_request = GovernanceRequest(
        action=ActionType.DELETE_DATA,
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        await service.evaluate_and_record(first_request)
        await service.evaluate_and_record(second_request)

        repository = GovernanceAuditRepository(session)
        records = await repository.list_recent(limit=2)

    assert len(records) == 2
    assert all(record.id for record in records)


async def test_external_target_is_preserved_in_audit() -> None:
    target = "https://example.invalid/api"
    request = GovernanceRequest(
        action=ActionType.EXTERNAL_API_CALL,
        external_target=target,
    )

    async with AsyncSessionFactory() as session:
        service = GovernanceService(session)
        evaluation = await service.evaluate_and_record(request)

    assert evaluation.result.decision is GovernanceDecision.DENY
    assert evaluation.audit_entry.external_target == target