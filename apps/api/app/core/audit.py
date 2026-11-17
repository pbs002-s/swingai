"""Audit log helper: every config change, review and approval is recorded (PRD F-AUD-1)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def audit(
    db: AsyncSession,
    actor_user_id: int | None,
    action: str,
    entity: str,
    entity_id: Any = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity=entity,
            entity_id=None if entity_id is None else str(entity_id),
            detail=detail,
            ip=ip,
        )
    )
