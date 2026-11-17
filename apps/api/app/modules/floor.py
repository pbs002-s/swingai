"""Live floor, admin overview and station timeline (docs/API.md §10, §15)."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, utcnow
from app.core.errors import not_found, ok
from app.core.security import current_user
from app.models import (
    Alert,
    Device,
    Event,
    Factory,
    Floor,
    Line,
    Operation,
    ProductionEntry,
    Station,
    StationLive,
    User,
    Worker,
    WorkerAssignment,
)
from app.modules.shift import DEFAULT_THRESHOLDS, ShiftWindow, current_shift, policy_body

router = APIRouter(tags=["floor"])
DEVICE_STALE = timedelta(minutes=3)


def tile_state(live: StationLive | None, now: datetime, down_after: float) -> str:
    """One display state per station: running | idle | down | break | no_data."""
    if live is None or live.worker_state in (None, "uncertain"):
        return "no_data"
    if live.worker_state == "break":
        return "break"
    if live.machine_state == "stopped" and live.machine_since and now - live.machine_since > timedelta(minutes=down_after):
        return "down"
    if live.worker_state == "working":
        return "running"
    return "idle"


async def _factory(db: AsyncSession, factory_id: int | None) -> Factory:
    q = select(Factory).order_by(Factory.id)
    f = (await db.execute(q.where(Factory.id == factory_id) if factory_id else q.limit(1))).scalars().first()
    if f is None:
        raise not_found("Factory")
    return f


async def _stations(db: AsyncSession, factory_id: int, line_id: int | None = None) -> list[tuple[Station, Line]]:
    q = (
        select(Station, Line)
        .join(Line, Line.id == Station.line_id)
        .join(Floor, Floor.id == Line.floor_id)
        .where(Floor.factory_id == factory_id, Station.status != "inactive")
        .order_by(Line.id, Station.position)
    )
    if line_id:
        q = q.where(Line.id == line_id)
    return [(s, ln) for s, ln in (await db.execute(q)).all()]


async def _assignments(db: AsyncSession, station_ids: list[int], at: datetime) -> dict[int, tuple[Worker, Operation]]:
    q = (
        select(WorkerAssignment.station_id, Worker, Operation)
        .join(Worker, Worker.id == WorkerAssignment.worker_id)
        .join(Operation, Operation.id == WorkerAssignment.operation_id)
        .where(
            WorkerAssignment.station_id.in_(station_ids),
            WorkerAssignment.valid_from <= at,
            or_(WorkerAssignment.valid_to.is_(None), WorkerAssignment.valid_to > at),
        )
    )
    return {sid: (w, op) for sid, w, op in (await db.execute(q)).all()}


async def _staffed_minutes(db: AsyncSession, station_ids: list[int], shift: ShiftWindow, now: datetime) -> dict[int, float]:
    """Scheduled minutes each station has had someone assigned this shift (mid-shift starts count from their start)."""
    first = func.min(func.greatest(WorkerAssignment.valid_from, shift.start))
    q = (
        select(WorkerAssignment.station_id, first)
        .where(
            WorkerAssignment.station_id.in_(station_ids),
            WorkerAssignment.valid_from < now,
            or_(WorkerAssignment.valid_to.is_(None), WorkerAssignment.valid_to > shift.start),
        )
        .group_by(WorkerAssignment.station_id)
    )
    worked_now = shift.worked_minutes(now)
    return {sid: worked_now - shift.worked_minutes(start) for sid, start in (await db.execute(q)).all()}


async def _output(db: AsyncSession, station_ids: list[int], shift: ShiftWindow) -> dict[int, int]:
    q = (
        select(ProductionEntry.station_id, func.sum(ProductionEntry.qty_accepted))
        .where(
            ProductionEntry.station_id.in_(station_ids),
            ProductionEntry.period_end > shift.start,
            ProductionEntry.period_start < shift.end,
        )
        .group_by(ProductionEntry.station_id)
    )
    return {sid: int(n or 0) for sid, n in (await db.execute(q)).all()}


def _target(op: Operation | None, minutes: float, eff_pct: float) -> float:
    return 0.0 if op is None else minutes / float(op.smv) * eff_pct / 100


async def _context(db: AsyncSession, factory_id: int | None, line_id: int | None = None) -> dict[str, Any]:
    factory = await _factory(db, factory_id)
    shift, now = await current_shift(db, factory), utcnow()
    th = await policy_body(db, factory.id, "thresholds", DEFAULT_THRESHOLDS)
    rows = await _stations(db, factory.id, line_id)
    ids = [s.id for s, _ in rows]
    lives = {lv.station_id: lv for lv in (await db.execute(select(StationLive).where(StationLive.station_id.in_(ids)))).scalars()}
    return {
        "factory": factory,
        "shift": shift,
        "now": now,
        "th": th,
        "rows": rows,
        "ids": ids,
        "lives": lives,
        "assign": await _assignments(db, ids, now),
        "output": await _output(db, ids, shift),
        "minutes": shift.worked_minutes(now),
        "staffed": await _staffed_minutes(db, ids, shift, now),
    }


def _shift_out(shift: ShiftWindow) -> dict[str, Any]:
    return {
        "start": shift.start.isoformat(),
        "end": shift.end.isoformat(),
        "breaks": [[a.isoformat(), b.isoformat()] for a, b in shift.breaks],
    }


@router.get("/overview")
async def overview(factory_id: int | None = None, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    c = await _context(db, factory_id)
    eff_target, now = float(c["th"]["target_efficiency_pct"]), c["now"]
    lines: dict[int, dict[str, Any]] = {}
    totals = defaultdict(float)
    for s, ln in c["rows"]:
        L = lines.setdefault(
            ln.id,
            {
                "id": ln.id,
                "code": ln.code,
                "name": ln.name,
                "operation": None,
                "states": defaultdict(int),
                "output": 0,
                "target": 0.0,
                "earned_min": 0.0,
                "staffed_min": 0.0,
                "open_alerts": {"critical": 0, "warning": 0, "info": 0},
            },
        )
        st = tile_state(c["lives"].get(s.id), now, c["th"]["down_after_min"])
        L["states"][st] += 1
        totals[st] += 1
        wa = c["assign"].get(s.id)
        out = c["output"].get(s.id, 0)
        L["output"] += out
        if wa:
            L["operation"] = L["operation"] or wa[1].name
            L["target"] += _target(wa[1], c["staffed"].get(s.id, 0.0), eff_target)
            L["earned_min"] += out * float(wa[1].smv)
            L["staffed_min"] += c["staffed"].get(s.id, 0.0)
    alert_rows = (
        await db.execute(
            select(Station.line_id, Alert.severity, func.count())
            .join(Station, Station.id == Alert.station_id)
            .where(Alert.status.in_(["open", "acknowledged"]), Station.id.in_(c["ids"]))
            .group_by(Station.line_id, Alert.severity)
        )
    ).all()
    for line_id, sev, n in alert_rows:
        if line_id in lines:
            lines[line_id]["open_alerts"][sev] = n
    sev_counts = dict(
        (
            await db.execute(
                select(Alert.severity, func.count()).where(Alert.status.in_(["open", "acknowledged"])).group_by(Alert.severity)
            )
        ).all()
    )
    out_lines = []
    for L in lines.values():
        L["states"] = dict(L["states"])
        L["efficiency_pct"] = round(L["earned_min"] / L["staffed_min"] * 100, 1) if L["staffed_min"] else None
        L["target"] = round(L["target"])
        out_lines.append({k: v for k, v in L.items() if k not in ("earned_min", "staffed_min")})
    earned = sum(x["earned_min"] for x in lines.values())
    staffed = sum(x["staffed_min"] for x in lines.values())
    return ok(
        {
            "as_of": now.isoformat(),
            "factory": {"id": c["factory"].id, "name": c["factory"].name},
            "shift": _shift_out(c["shift"]),
            "totals": {
                "stations": len(c["rows"]),
                "states": {k: int(v) for k, v in totals.items()},
                "output": sum(x["output"] for x in out_lines),
                "target": sum(x["target"] for x in out_lines),
                "efficiency_pct": round(earned / staffed * 100, 1) if staffed else None,
                "target_efficiency_pct": eff_target,
                "open_alerts": {s: sev_counts.get(s, 0) for s in ("critical", "warning", "info")},
            },
            "lines": out_lines,
            "hourly": await _hourly(db, c["ids"], c["shift"]),
            "devices": await _devices(db, now),
        }
    )


async def _hourly(db: AsyncSession, ids: list[int], shift: ShiftWindow) -> list[dict[str, Any]]:
    local_hour = func.date_trunc("hour", func.timezone(str(shift.tz), ProductionEntry.period_start)).label("h")
    q = (
        select(local_hour, func.sum(ProductionEntry.qty_accepted))
        .where(
            ProductionEntry.station_id.in_(ids),
            ProductionEntry.period_end > shift.start,
            ProductionEntry.period_start < shift.end,
        )
        .group_by(local_hour)
    )
    by_hour = {h.hour: int(n or 0) for h, n in (await db.execute(q)).all()}
    hours, t = [], shift.start
    while t < shift.end:
        local = t.astimezone(shift.tz)
        hours.append({"hour": local.strftime("%H:00"), "output": by_hour.get(local.hour, 0), "is_break": shift.in_break(t)})
        t += timedelta(hours=1)
    return hours


async def _devices(db: AsyncSession, now: datetime) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Device.kind, Device.last_seen_at).where(Device.is_active))).all()
    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "online": 0})
    for kind, seen in rows:
        agg[kind]["total"] += 1
        agg[kind]["online"] += int(bool(seen and now - seen < DEVICE_STALE))
    return [{"kind": k, **v} for k, v in sorted(agg.items())]


@router.get("/floor")
async def floor(line_id: int = Query(...), db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    c = await _context(db, None, line_id)
    if not c["rows"]:
        raise not_found("Line")
    pending = dict(
        (
            await db.execute(
                select(Event.station_id, func.count())
                .where(Event.review_status == "pending", Event.station_id.in_(c["ids"]), Event.start_time >= c["shift"].start)
                .group_by(Event.station_id)
            )
        ).all()
    )
    stations = []
    for s, _ln in c["rows"]:
        live, wa = c["lives"].get(s.id), c["assign"].get(s.id)
        stations.append(
            {
                "id": s.id,
                "code": s.code,
                "position": s.position,
                "state": tile_state(live, c["now"], c["th"]["down_after_min"]),
                "worker_state": live.worker_state if live else None,
                "since": live.worker_since.isoformat() if live and live.worker_since else None,
                "worker": {"id": wa[0].id, "name": wa[0].full_name, "name_bn": wa[0].full_name_bn} if wa else None,
                "operation": {"id": wa[1].id, "name": wa[1].name, "smv": float(wa[1].smv)} if wa else None,
                "output": c["output"].get(s.id, 0),
                "target": round(
                    _target(wa[1] if wa else None, c["staffed"].get(s.id, 0.0), float(c["th"]["target_efficiency_pct"]))
                ),
                "pending_reviews": pending.get(s.id, 0),
            }
        )
    ln = c["rows"][0][1]
    return ok(
        {
            "line": {"id": ln.id, "code": ln.code, "name": ln.name},
            "shift": _shift_out(c["shift"]),
            "as_of": c["now"].isoformat(),
            "stations": stations,
        }
    )


@router.get("/stations/{station_id}/timeline")
async def timeline(station_id: int, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    station = await db.get(Station, station_id)
    if station is None:
        raise not_found("Station")
    line = await db.get(Line, station.line_id)
    fl = await db.get(Floor, line.floor_id) if line else None
    factory = await _factory(db, fl.factory_id if fl else None)
    shift, now = await current_shift(db, factory), utcnow()
    q = (
        select(Event)
        .where(
            Event.station_id == station_id,
            Event.event_type.in_(["worker_state", "machine_state"]),
            Event.start_time >= shift.start - timedelta(hours=1),
            Event.start_time < shift.end,
            Event.review_status != "rejected",
        )
        .order_by(Event.start_time)
    )
    events = list((await db.execute(q)).scalars())
    lanes: dict[str, list[dict[str, Any]]] = {"worker_state": [], "machine_state": []}
    for e in events:
        lane = lanes[e.event_type]
        start = max(e.start_time, shift.start)
        if lane:
            lane[-1]["end"] = start.isoformat()
        lane.append(
            {
                "state": e.state,
                "start": start.isoformat(),
                "end": None,
                "event_id": e.id,
                "review_status": e.review_status,
                "confidence": float(e.confidence) if e.confidence else None,
            }
        )
    for lane in lanes.values():
        if lane:
            lane[-1]["end"] = min(now, shift.end).isoformat()
    minutes: dict[str, float] = defaultdict(float)
    for seg in lanes["worker_state"]:
        minutes[seg["state"]] += (datetime.fromisoformat(seg["end"]) - datetime.fromisoformat(seg["start"])).total_seconds() / 60
    wa = (await _assignments(db, [station_id], now)).get(station_id)
    out = (await _output(db, [station_id], shift)).get(station_id, 0)
    eff = round(out * float(wa[1].smv) / shift.worked_minutes(now) * 100, 1) if wa and shift.worked_minutes(now) else None
    return ok(
        {
            "station": {"id": station.id, "code": station.code, "line": line.name if line else None},
            "worker": {"id": wa[0].id, "name": wa[0].full_name} if wa else None,
            "operation": {"name": wa[1].name, "smv": float(wa[1].smv)} if wa else None,
            "shift": _shift_out(shift),
            "lanes": lanes,
            "minutes": {k: round(v, 1) for k, v in minutes.items()},
            "output": out,
            "efficiency_pct": eff,
        }
    )


__all__ = ["router", "tile_state"]
