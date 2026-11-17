"""Event ingestion (docs/API.md §9). Shared by the HTTP endpoint, the simulator and manual entry."""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import bus
from app.core.db import get_session, utcnow
from app.core.errors import ok
from app.core.security import current_device
from app.models import Device, Event, MachineAssignment, Station, StationLive, WorkerAssignment
from app.models.events import ALWAYS_REVIEW, EVENT_STATES

router = APIRouter(prefix="/ingest", tags=["ingest"])
REVIEW_THRESHOLD = Decimal("0.75")


class EventIn(BaseModel):
    event_uuid: uuid.UUID
    event_type: Literal["worker_state", "machine_state", "production_count", "needle_event", "quality_event", "rfid_tap"]
    state: str = Field(min_length=1, max_length=32)
    station_code: str = Field(min_length=1, max_length=32)
    start_time: datetime
    end_time: datetime | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    model_version: str | None = Field(default=None, max_length=48)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=32)

    @field_validator("start_time", "end_time")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamps must include a time zone (use UTC, e.g. 2026-11-17T09:12:03Z)")
        return v


class BatchIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=500)


def review_status(event_type: str, state: str, confidence: Decimal | None) -> str:
    if (event_type, state) in ALWAYS_REVIEW or (event_type, "*") in ALWAYS_REVIEW:
        return "pending"
    if confidence is not None and confidence < REVIEW_THRESHOLD:
        return "pending"
    return "auto_accepted"


MAX_FUTURE = timedelta(minutes=5)  # clock skew allowed from devices
MAX_PAST = timedelta(days=7)  # edge outbox holds 72 h; older data is a bug or an attack
MAX_META_BYTES = 4096


class _Assignments:
    """Machine and worker assignments for a batch's stations, loaded once (no per-event queries)."""

    def __init__(self, rows: dict[int, list[Any]]):
        self.rows = rows

    @classmethod
    async def load(cls, db: AsyncSession, model: Any, station_ids: list[int], since: datetime) -> "_Assignments":
        q = select(model).where(model.station_id.in_(station_ids), or_(model.valid_to.is_(None), model.valid_to > since))
        rows: dict[int, list[Any]] = {}
        for r in (await db.execute(q.order_by(model.valid_from.desc()))).scalars():
            rows.setdefault(r.station_id, []).append(r)
        return cls(rows)

    def at(self, station_id: int, when: datetime) -> Any:
        for r in self.rows.get(station_id, []):
            if r.valid_from <= when and (r.valid_to is None or r.valid_to > when):
                return r
        return None


async def _lock_live(db: AsyncSession, station_ids: list[int]) -> dict[int, StationLive]:
    """Create missing live rows race-free, then lock the batch's rows for update."""
    if station_ids:
        await db.execute(
            pg_insert(StationLive)
            .values([{"station_id": i} for i in station_ids])
            .on_conflict_do_nothing(index_elements=["station_id"])
        )
    q = select(StationLive).where(StationLive.station_id.in_(station_ids)).order_by(StationLive.station_id).with_for_update()
    return {lv.station_id: lv for lv in (await db.execute(q)).scalars()}


def _update_live(live: StationLive, event_type: str, state: str, at: datetime) -> bool:
    """Move live state forward. False for an older transition or a repeat of the same state (keeps `since`)."""
    cur_state, cur_since = (
        (live.worker_state, live.worker_since) if event_type == "worker_state" else (live.machine_state, live.machine_since)
    )
    if (cur_since and at < cur_since) or cur_state == state:
        return False
    if event_type == "worker_state":
        live.worker_state, live.worker_since = state, at
    else:
        live.machine_state, live.machine_since = state, at
    live.updated_at = utcnow()
    return True


def _check(e: EventIn, station: Station | None, device: Device | None) -> str | None:
    if station is None:
        return "UNKNOWN_STATION"
    if device is not None and device.kind != "edge_box" and device.station_id != station.id:
        return "DEVICE_STATION_MISMATCH"
    if e.state not in EVENT_STATES[e.event_type]:
        return "INVALID_EVENT_TYPE"
    now = utcnow()
    if e.start_time > now + MAX_FUTURE:
        return "TIME_IN_FUTURE"
    if e.start_time < now - MAX_PAST:
        return "TIME_TOO_OLD"
    if len(json.dumps(e.metadata, default=str)) > MAX_META_BYTES:
        return "METADATA_TOO_LARGE"
    return None


async def ingest_batch(db: AsyncSession, events: list[EventIn], source: str, device: Device | None) -> dict[str, Any]:
    stations = {
        s.code: s for s in (await db.execute(select(Station).where(Station.code.in_({e.station_code for e in events})))).scalars()
    }
    ids = sorted({s.id for s in stations.values()})
    since = min(e.start_time for e in events)
    machines = await _Assignments.load(db, MachineAssignment, ids, since)
    workers = await _Assignments.load(db, WorkerAssignment, ids, since)
    lives = await _lock_live(db, ids)
    results, counts, published = [], {"accepted": 0, "duplicate": 0, "rejected": 0}, []
    for e in sorted(events, key=lambda x: x.start_time):
        station = stations.get(e.station_code)
        error = _check(e, station, device)
        if error or station is None:
            counts["rejected"] += 1
            results.append({"event_uuid": str(e.event_uuid), "status": "rejected", "event_id": None, "error": error})
            continue
        m, w = machines.at(station.id, e.start_time), workers.at(station.id, e.start_time)
        status_ = review_status(e.event_type, e.state, e.confidence)
        stmt = (
            pg_insert(Event)
            .values(
                event_uuid=e.event_uuid,
                event_type=e.event_type,
                state=e.state,
                station_id=station.id,
                machine_id=m.machine_id if m else None,
                worker_id=w.worker_id if w else None,
                operation_id=w.operation_id if w else None,
                source=source,
                device_id=device.id if device else None,
                start_time=e.start_time,
                end_time=e.end_time,
                confidence=e.confidence,
                model_version=e.model_version,
                review_status=status_,
                meta=e.metadata,
                received_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=["event_uuid"])
            .returning(Event.id)
        )
        event_id = (await db.execute(stmt)).scalar_one_or_none()
        if event_id is None:
            counts["duplicate"] += 1
            results.append({"event_uuid": str(e.event_uuid), "status": "duplicate", "event_id": None, "error": None})
            continue
        counts["accepted"] += 1
        results.append({"event_uuid": str(e.event_uuid), "status": "accepted", "event_id": event_id, "error": None})
        if e.event_type in ("worker_state", "machine_state") and _update_live(
            lives[station.id], e.event_type, e.state, e.start_time
        ):
            published.append(
                (
                    "station_state",
                    {
                        "station_id": station.id,
                        "line_id": station.line_id,
                        "type": e.event_type,
                        "state": e.state,
                        "since": e.start_time.isoformat(),
                    },
                )
            )
        if status_ == "pending":
            published.append(("review_added", {"event_id": event_id, "station_id": station.id, "line_id": station.line_id}))
    if device is not None:
        device.last_seen_at = utcnow()
    await db.commit()
    for kind, data in published:  # only after the commit, so listeners never see rolled-back data
        bus.publish(kind, data)
    return {**counts, "results": results}


@router.post("/events")
async def post_events(body: BatchIn, device: Device = Depends(current_device), db: AsyncSession = Depends(get_session)):
    source = "vision" if device.kind == "camera" else "sensor"
    return ok(await ingest_batch(db, body.events, source, device))


@router.post("/heartbeat")
async def heartbeat(device: Device = Depends(current_device), db: AsyncSession = Depends(get_session)):
    device.last_seen_at = utcnow()
    await db.commit()
    return ok({"device": device.code, "at": device.last_seen_at.isoformat()})


__all__ = ["EventIn", "ingest_batch", "router"]
