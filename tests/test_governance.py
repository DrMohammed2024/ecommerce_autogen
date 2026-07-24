from decimal import Decimal

from app.governance import (
    ActionType,
    GovernanceDecision,
    GovernancePolicy,
    GovernanceRequest,
    evaluate_request,
)


def test_low_value_action_is_allowed() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("50.00"),
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.ALLOW
    assert result.requires_human is False


def test_action_above_automatic_limit_requires_approval() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("250.00"),
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.REQUIRE_APPROVAL
    assert result.requires_human is True


def test_human_approved_action_is_allowed_within_hard_limit() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("250.00"),
        human_approved=True,
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.ALLOW
    assert result.requires_human is False


def test_action_above_maximum_limit_is_denied() -> None:
    request = GovernanceRequest(
        action=ActionType.CREATE_ORDER,
        amount=Decimal("1500.00"),
        human_approved=True,
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.DENY


def test_payment_is_denied_without_execution() -> None:
    request = GovernanceRequest(
        action=ActionType.ISSUE_PAYMENT,
        amount=Decimal("25.00"),
        human_approved=True,
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.DENY
    assert "Payment execution is disabled" in result.reasons[0]


def test_external_api_call_is_denied() -> None:
    request = GovernanceRequest(
        action=ActionType.EXTERNAL_API_CALL,
        external_target="https://example.invalid/api",
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.DENY
    assert "External actions are disabled" in result.reasons[0]


def test_external_message_is_denied() -> None:
    request = GovernanceRequest(
        action=ActionType.SEND_MESSAGE,
        external_target="customer@example.com",
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.DENY


def test_custom_policy_can_allow_external_action() -> None:
    policy = GovernancePolicy(
        block_external_actions=False,
    )
    request = GovernanceRequest(
        action=ActionType.EXTERNAL_API_CALL,
        external_target="https://example.invalid/api",
    )

    result = evaluate_request(request, policy)

    assert result.decision is GovernanceDecision.ALLOW


def test_payment_remains_denied_even_with_human_approval() -> None:
    request = GovernanceRequest(
        action=ActionType.ISSUE_PAYMENT,
        amount=Decimal("10.00"),
        human_approved=True,
    )

    result = evaluate_request(request)

    assert result.decision is GovernanceDecision.DENY
