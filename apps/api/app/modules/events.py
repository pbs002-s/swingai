"""Review queue and event reviews (docs/API.md §10). Raw events are never edited."""

from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import bus
from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import check_line_scope, client_ip, current_user, require_roles
from app.models import Event, EventReview, Line, Station, User, Worker
from app.models.events import EVENT_STATES

router = APIRouter(prefix="/events", tags=["events"])
REVIEWERS = ("supervisor", "quality", "maintenance", "factory_admin")

TITLES = {
    ("worker_state", "phone_use"): "Possible phone use",
    ("worker_state", "idle"): "Idle, low confidence",
    ("worker_state", "away"): "Away from station",
    ("needle_event", "suspected_break"): "Suspected needle break",
    ("needle_event", "needle_break"): "Needle break",
    ("quality_event", "possible_skipped_stitch"): "Possible skipped stitch",
    ("quality_event", "possible_puckering"): "Possible puckering",
}


async def _next_start(db: AsyncSession, e: Event) -> Any:
    q = select(func.min(Event.start_time)).where(
        Event.station_id == e.station_id, Event.event_type == e.event_type, Event.start_time > e.start_time
    )
    return (await db.execute(q)).scalar_one_or_none()


@router.get("/review-queue")
async def review_queue(
    line_id: int | None = None, limit: int = 50, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)
):
    limit = max(1, min(limit, 200))
    q = (
        select(Event, Station, Line, Worker)
        .join(Station, Station.id == Event.station_id)
        .join(Line, Line.id == Station.line_id)
        .outerjoin(Worker, Worker.id == Event.worker_id)
        .where(Event.review_status == "pending")
        .order_by(Event.start_time.desc())
    )
    if line_id:
        q = q.where(Line.id == line_id)
    total_q = select(func.count()).select_from(Event).where(Event.review_status == "pending")
    if line_id:
        total_q = total_q.join(Station, Station.id == Event.station_id).where(Station.line_id == line_id)
    total = (await db.execute(total_q)).scalar_one()
    items = []
    for e, s, ln, w in (await db.execute(q.limit(limit))).all():
        end = e.end_time or await _next_start(db, e)
        items.append(
            {
                "id": e.id,
                "event_type": e.event_type,
                "state": e.state,
                "title": TITLES.get((e.event_type, e.state), f"{e.event_type} · {e.state}"),
                "station": {"id": s.id, "code": s.code},
                "line": {"id": ln.id, "name": ln.name},
                "worker": {"id": w.id, "name": w.full_name} if w else None,
                "start_time": e.start_time.isoformat(),
                "duration_s": round((end - e.start_time).total_seconds()) if end else None,
                "confidence": float(e.confidence) if e.confidence is not None else None,
                "source": e.source,
                "model_version": e.model_version,
                "meta": e.meta,
            }
        )
    return ok(items, {"total": total, "limit": limit})


class ReviewIn(BaseModel):
    decision: Literal["confirm", "reject", "reclassify"]
    new_state: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _state_needed(self) -> "ReviewIn":
        if self.decision == "reclassify" and not self.new_state:
            raise ValueError("new_state is required to reclassify")
        return self


@router.post("/{event_id}/review")
async def review(
    event_id: int,
    body: ReviewIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(*REVIEWERS)),
):
    e = await db.get(Event, event_id, with_for_update=True)
    if e is None:
        raise not_found("Event")
    station = await db.get(Station, e.station_id)
    check_line_scope(user, station.line_id if station else -1)
    if e.review_status in ("confirmed", "rejected", "reclassified"):
        raise AppError(409, "ALREADY_REVIEWED", "Someone has already reviewed this event.")
    if body.decision == "reclassify" and body.new_state not in EVENT_STATES[e.event_type]:
        raise AppError(400, "VALIDATION_ERROR", "That state does not exist for this event type.")
    db.add(EventReview(event_id=e.id, decision=body.decision, new_state=body.new_state, note=body.note, reviewed_by=user.id))
    e.review_status = {"confirm": "confirmed", "reject": "rejected", "reclassify": "reclassified"}[body.decision]
    audit(
        db, user.id, f"event.{body.decision}", "event", e.id, {"new_state": body.new_state, "note": body.note}, client_ip(request)
    )
    await db.commit()
    bus.publish("review_done", {"event_id": e.id, "station_id": e.station_id})
    return ok({"id": e.id, "review_status": e.review_status, "reviewed_at": utcnow().isoformat()})


__all__ = ["router", "timedelta"]
