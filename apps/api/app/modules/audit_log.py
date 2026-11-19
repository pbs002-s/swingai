"""Read-only audit log for factory admins (PRD F-AUD-1). Rows are written by `core.audit.audit`; nothing edits them."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ok
from app.core.security import require_roles
from app.models import AuditLog, User

router = APIRouter(tags=["audit"])
MAX_PAGE = 100


@router.get("/audit-logs")
async def list_audit_logs(
    user_id: int | None = None,
    entity: str | None = Query(default=None, max_length=64),
    action: str | None = Query(default=None, max_length=64),
    since: datetime | None = None,
    until: datetime | None = None,
    before_id: int | None = Query(default=None, ge=1, description="Keyset paging: rows older than this id"),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE),
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("factory_admin")),
):
    q = select(AuditLog, User.full_name, User.email).join(User, User.id == AuditLog.actor_user_id, isouter=True)
    if user_id is not None:
        q = q.where(AuditLog.actor_user_id == user_id)
    if entity:
        q = q.where(AuditLog.entity == entity)
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))  # "camera" finds camera.create, camera.zones ...
    if since:
        q = q.where(AuditLog.at >= since)
    if until:
        q = q.where(AuditLog.at < until)
    if before_id:
        q = q.where(AuditLog.id < before_id)
    rows = (await db.execute(q.order_by(AuditLog.id.desc()).limit(limit + 1))).all()
    page = rows[:limit]
    items: list[dict[str, Any]] = [
        {
            "id": a.id,
            "at": a.at.isoformat(),
            "actor": {"id": a.actor_user_id, "name": name, "email": email} if a.actor_user_id else None,
            "action": a.action,
            "entity": a.entity,
            "entity_id": a.entity_id,
            "detail": a.detail,
            "ip": a.ip,
        }
        for a, name, email in page
    ]
    return ok(items, meta={"next_before_id": items[-1]["id"] if len(rows) > limit else None})
