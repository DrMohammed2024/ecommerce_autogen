from app.governance.models import (
    ActionType,
    GovernanceDecision,
    GovernancePolicy,
    GovernanceRequest,
    GovernanceResult,
)

EXTERNAL_ACTIONS = frozenset(
    {
        ActionType.EXTERNAL_API_CALL,
        ActionType.SEND_MESSAGE,
    }
)


def evaluate_request(
    request: GovernanceRequest,
    policy: GovernancePolicy | None = None,
) -> GovernanceResult:
    """Evaluate an action without executing it."""

    active_policy = policy or GovernancePolicy()

    if request.action is ActionType.ISSUE_PAYMENT and active_policy.block_payments:
        return GovernanceResult(
            request_id=request.id,
            decision=GovernanceDecision.DENY,
            reasons=(
                "Payment execution is disabled by the local governance policy.",
            ),
        )

    if (
        request.action in EXTERNAL_ACTIONS
        and active_policy.block_external_actions
    ):
        return GovernanceResult(
            request_id=request.id,
            decision=GovernanceDecision.DENY,
            reasons=(
                "External actions are disabled by the local governance policy.",
            ),
        )

    if request.amount > active_policy.max_human_approved_amount:
        return GovernanceResult(
            request_id=request.id,
            decision=GovernanceDecision.DENY,
            reasons=(
                "The requested amount exceeds the maximum permitted amount.",
            ),
        )

    if request.amount > active_policy.max_automatic_amount:
        if not request.human_approved:
            return GovernanceResult(
                request_id=request.id,
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                reasons=(
                    "The requested amount requires explicit human approval.",
                ),
                requires_human=True,
            )

        return GovernanceResult(
            request_id=request.id,
            decision=GovernanceDecision.ALLOW,
            reasons=(
                "The requested amount has explicit human approval.",
            ),
        )

    return GovernanceResult(
        request_id=request.id,
        decision=GovernanceDecision.ALLOW,
        reasons=(
            "The requested action is within the automatic policy limits.",
        ),
    )