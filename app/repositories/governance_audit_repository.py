import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.audit_models import GovernanceAuditRecord
from app.governance.audit import GovernanceAuditEntry
from app.governance.models import (
    ActionType,
    GovernanceDecision,
    GovernanceRequest,
    GovernanceResult,
)
from app.models.common import Currency


class GovernanceAuditRepository:
    """Persists and retrieves local governance audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        request: GovernanceRequest,
        result: GovernanceResult,
    ) -> GovernanceAuditEntry:
        """Persist one governance decision and return its audit entry."""

        record = GovernanceAuditRecord(
            request_id=str(request.id),
            action=request.action.value,
            amount=request.amount,
            currency=request.currency.value,
            human_approved=request.human_approved,
            decision=result.decision.value,
            requires_human=result.requires_human,
            reasons_json=json.dumps(list(result.reasons)),
            external_target=request.external_target,
        )

        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        return self._to_entry(record)

    async def get_by_id(
        self,
        record_id: UUID,
    ) -> GovernanceAuditEntry | None:
        """Return one audit entry by its record identifier."""

        record = await self._session.get(
            GovernanceAuditRecord,
            str(record_id),
        )

        if record is None:
            return None

        return self._to_entry(record)

    async def get_by_request_id(
        self,
        request_id: UUID,
    ) -> GovernanceAuditEntry | None:
        """Return the most recent entry for a governance request."""

        statement = (
            select(GovernanceAuditRecord)
            .where(GovernanceAuditRecord.request_id == str(request_id))
            .order_by(GovernanceAuditRecord.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_entry(record)

    async def list_recent(
        self,
        limit: int = 100,
    ) -> tuple[GovernanceAuditEntry, ...]:
        """Return recent audit entries, newest first."""

        safe_limit = max(1, min(limit, 500))
        statement = (
            select(GovernanceAuditRecord)
            .order_by(GovernanceAuditRecord.created_at.desc())
            .limit(safe_limit)
        )
        result = await self._session.execute(statement)
        records: Sequence[GovernanceAuditRecord] = result.scalars().all()

        return tuple(self._to_entry(record) for record in records)

    @staticmethod
    def _to_entry(
        record: GovernanceAuditRecord,
    ) -> GovernanceAuditEntry:
        """Convert a database record to a validated domain entry."""

        raw_reasons = json.loads(record.reasons_json)

        if not isinstance(raw_reasons, list) or not all(
            isinstance(reason, str) for reason in raw_reasons
        ):
            raise ValueError("Stored audit reasons are invalid.")

        return GovernanceAuditEntry(
            id=UUID(record.id),
            request_id=UUID(record.request_id),
            action=ActionType(record.action),
            amount=record.amount,
            currency=Currency(record.currency),
            human_approved=record.human_approved,
            decision=GovernanceDecision(record.decision),
            requires_human=record.requires_human,
            reasons=tuple(raw_reasons),
            external_target=record.external_target,
            created_at=record.created_at,
        )