"""Retention purge: removes expired data, keeps everything else, and records that it ran."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.core.db import utcnow
from app.models import Alert, AuditLog, Event, EventReview, Station, User
from app.modules.maintenance import purge_expired


def _event(station_id: int, age_days: float, tag: str) -> Event:
    return Event(
        event_uuid=uuid.uuid4(),
        event_type="worker_state",
        state="working",
        station_id=station_id,
        source="simulator",
        start_time=utcnow() - timedelta(days=age_days),
        review_status="auto_accepted",
        meta={"tag": tag},
    )


async def test_purge_removes_only_expired_rows_and_unlinks_references(admin, db):
    station = (await db.execute(select(Station.id).limit(1))).scalar_one()
    user = (await db.execute(select(User.id).limit(1))).scalar_one()
    old, fresh = _event(station, 4000, "purge-old"), _event(station, 2, "purge-fresh")  # default retention is 365 days
    db.add_all([old, fresh])
    await db.flush()
    db.add(EventReview(event_id=old.id, decision="confirm", reviewed_by=user))
    alert = Alert(
        dedupe_key=f"purge-{uuid.uuid4()}",
        type="t",
        severity="info",
        station_id=station,
        event_id=old.id,
        title="keep me",
        detail="x",
    )
    db.add(alert)
    db.add(AuditLog(actor_user_id=user, action="ancient.thing", entity="x", at=utcnow() - timedelta(days=4000)))
    await db.commit()
    old_id, fresh_id, alert_id = old.id, fresh.id, alert.id

    result = await purge_expired(db)
    assert result["events"] >= 1 and result["audit_logs"] >= 1

    assert await db.get(Event, old_id) is None
    assert await db.get(Event, fresh_id) is not None  # inside the retention period
    kept = await db.get(Alert, alert_id)
    await db.refresh(kept)
    assert kept is not None and kept.event_id is None  # the alert stays, only the link goes
    assert (
        await db.execute(select(func.count()).select_from(EventReview).where(EventReview.event_id == old_id))
    ).scalar_one() == 0
    ran = (
        (await db.execute(select(AuditLog).where(AuditLog.action == "retention.purge").order_by(AuditLog.id.desc())))
        .scalars()
        .first()
    )
    assert ran is not None and ran.detail["events"] >= 1

    again = await purge_expired(db)  # idempotent: nothing left to remove
    assert again["events"] == 0 and again["audit_logs"] == 0


async def test_purge_endpoint_is_admin_only(admin, supervisor):
    assert (await admin.post("/maintenance/purge")).status_code == 200
    assert (await supervisor.post("/maintenance/purge")).status_code == 403
