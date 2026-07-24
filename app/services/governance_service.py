from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.audit import GovernanceEvaluation
from app.governance.models import GovernancePolicy, GovernanceRequest
from app.governance.policies import evaluate_request
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
)


class GovernanceService:
    """Evaluates governance requests and stores every resulting decision."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = GovernanceAuditRepository(session)

    async def evaluate_and_record(
        self,
        request: GovernanceRequest,
        policy: GovernancePolicy | None = None,
    ) -> GovernanceEvaluation:
        """Evaluate a request and persist its decision locally."""

        result = evaluate_request(request, policy)
        audit_entry = await self._repository.add(request, result)

        return GovernanceEvaluation(
            request=request,
            result=result,
            audit_entry=audit_entry,
        )
