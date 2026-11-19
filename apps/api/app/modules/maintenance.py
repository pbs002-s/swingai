"""Scheduled upkeep: delete data past its retention period, and say so in the audit log.

Retention comes from the factory's "retention" policy (see policies.py). Raw activity events are deleted in small
batches; things that point at them (reviews, alerts, needle events) keep their own record and just lose the link.
Needle lots and production figures are not personal activity data and are not touched.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import SessionLocal, get_session, utcnow
from app.core.errors import ok
from app.core.security import client_ip, require_roles
from app.models import Alert, AuditLog, Event, EventReview, Factory, NeedleEvent, User
from app.modules.policies import DEFAULTS
from app.modules.shift import policy_body

log = logging.getLogger("stitchsense.maintenance")
router = APIRouter(tags=["maintenance"])

BATCH = 5000
RUN_EVERY_S = 6 * 3600  # purge is idempotent, so running more often than needed is harmless
FIRST_RUN_DELAY_S = 120


async def purge_expired(
    db: AsyncSession, now: datetime | None = None, actor_user_id: int | None = None, ip: str | None = None
) -> dict[str, Any]:
    """Delete events and audit rows older than the retention policy. Returns what was removed."""
    now = now or utcnow()
    factory = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one_or_none()
    if factory is None:
        return {"events": 0, "audit_logs": 0}
    policy = await policy_body(db, factory.id, "retention", DEFAULTS["retention"])
    events_cutoff = now - timedelta(days=int(policy["events_days"]))
    audit_cutoff = now - timedelta(days=int(policy["audit_days"]))

    events = 0
    while True:
        ids = list((await db.execute(select(Event.id).where(Event.start_time < events_cutoff).limit(BATCH))).scalars())
        if not ids:
            break
        await db.execute(delete(EventReview).where(EventReview.event_id.in_(ids)))
        await db.execute(update(Alert).where(Alert.event_id.in_(ids)).values(event_id=None))
        await db.execute(update(NeedleEvent).where(NeedleEvent.event_id.in_(ids)).values(event_id=None))
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()
        events += len(ids)
    old_audit = await db.execute(delete(AuditLog).where(AuditLog.at < audit_cutoff))
    audit_rows = old_audit.rowcount or 0
    result = {
        "events": events,
        "audit_logs": audit_rows,
        "events_before": events_cutoff.isoformat(),
        "audit_before": audit_cutoff.isoformat(),
    }
    if events or audit_rows:  # a purge that removed nothing is not news
        audit(db, actor_user_id, "retention.purge", "retention", None, result, ip)
        log.info("retention purge: %s events, %s audit rows", events, audit_rows)
    await db.commit()
    return result


async def purge_loop() -> None:
    await asyncio.sleep(FIRST_RUN_DELAY_S)
    while True:
        try:
            async with SessionLocal() as db:
                await purge_expired(db)
        except Exception:
            log.exception("retention purge failed")
        await asyncio.sleep(RUN_EVERY_S)


@router.post("/maintenance/purge")
async def run_purge(
    request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(require_roles("factory_admin"))
):
    """Run the retention purge now (it also runs by itself every few hours)."""
    return ok(await purge_expired(db, actor_user_id=user.id, ip=client_ip(request)))
