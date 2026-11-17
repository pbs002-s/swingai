"""Alert center, editable alert rules, and the rule engine (docs/API.md §17)."""

import logging
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import bus
from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import client_ip, current_user, require_roles
from app.models import Alert, AlertRule, Device, Event, Factory, Line, Station, StationLive, User
from app.modules.shift import ShiftWindow, current_shift

log = logging.getLogger("stitchsense.alerts")
router = APIRouter(tags=["alerts"])
SEVERITIES = ("critical", "warning", "info")


def alert_out(a: Alert, station: Station | None, line: Line | None) -> dict[str, Any]:
    return {
        "id": a.id,
        "type": a.type,
        "severity": a.severity,
        "title": a.title,
        "detail": a.detail,
        "status": a.status,
        "confidence": float(a.confidence) if a.confidence is not None else None,
        "event_id": a.event_id,
        "station": {"id": station.id, "code": station.code} if station else None,
        "line": {"id": line.id, "name": line.name} if line else None,
        "created_at": a.created_at.isoformat(),
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


@router.get("/alerts")
async def list_alerts(
    status: Literal["open", "acknowledged", "resolved", "active"] = "active",
    severity: str | None = None,
    line_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(current_user),
):
    limit = max(1, min(limit, 200))
    q = (
        select(Alert, Station, Line)
        .outerjoin(Station, Station.id == Alert.station_id)
        .outerjoin(Line, Line.id == Station.line_id)
        .order_by(Alert.created_at.desc())
    )
    q = q.where(Alert.status.in_(["open", "acknowledged"])) if status == "active" else q.where(Alert.status == status)
    if severity in SEVERITIES:
        q = q.where(Alert.severity == severity)
    if line_id:
        q = q.where(Line.id == line_id)
    rows = (await db.execute(q.limit(limit))).all()
    counts = dict(
        (
            await db.execute(
                select(Alert.severity, func.count()).where(Alert.status.in_(["open", "acknowledged"])).group_by(Alert.severity)
            )
        ).all()
    )
    return ok([alert_out(a, s, ln) for a, s, ln in rows], {"counts": {s: counts.get(s, 0) for s in SEVERITIES}})


async def _set_status(db: AsyncSession, alert_id: int, user: User, status: str, request: Request) -> dict[str, Any]:
    a = await db.get(Alert, alert_id)
    if a is None:
        raise not_found("Alert")
    if a.status == "resolved":
        raise AppError(409, "ALREADY_RESOLVED", "This alert is already resolved.")
    a.status = status
    if status == "acknowledged":
        a.acknowledged_by = user.id
    else:
        a.resolved_at = utcnow()
    audit(db, user.id, f"alert.{status}", "alert", a.id, ip=client_ip(request))
    await db.commit()
    bus.publish("alert_update", {"alert_id": a.id, "status": a.status})
    return ok({"id": a.id, "status": a.status})


@router.post("/alerts/{alert_id}/ack")
async def ack(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("supervisor", "maintenance", "quality", "factory_admin")),
):
    return await _set_status(db, alert_id, user, "acknowledged", request)


@router.post("/alerts/{alert_id}/resolve")
async def resolve(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("supervisor", "maintenance", "quality", "factory_admin")),
):
    return await _set_status(db, alert_id, user, "resolved", request)


def rule_out(r: AlertRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "kind": r.kind,
        "condition": r.condition,
        "severity": r.severity,
        "recipient_roles": r.recipient_roles,
        "is_enabled": r.is_enabled,
    }


@router.get("/alert-rules")
async def list_rules(db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    return ok([rule_out(r) for r in (await db.execute(select(AlertRule).order_by(AlertRule.id))).scalars()])


class RulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    severity: Literal["critical", "warning", "info"] | None = None
    is_enabled: bool | None = None
    condition: dict[str, float | int | str] | None = None


@router.patch("/alert-rules/{rule_id}")
async def patch_rule(
    rule_id: int,
    body: RulePatch,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    r = await db.get(AlertRule, rule_id)
    if r is None:
        raise not_found("Alert rule")
    before = rule_out(r)
    changes = body.model_dump(exclude_none=True)
    if "condition" in changes:
        unknown = set(changes["condition"]) - set(r.condition)
        if unknown:
            raise AppError(400, "VALIDATION_ERROR", f"Unknown condition fields: {', '.join(sorted(unknown))}")
        changes["condition"] = {**r.condition, **changes["condition"]}
    for k, v in changes.items():
        setattr(r, k, v)
    audit(db, user.id, "alert_rule.update", "alert_rule", r.id, {"before": before, "after": rule_out(r)}, client_ip(request))
    await db.commit()
    return ok(rule_out(r))


# ---------------------------------------------------------------- engine


async def _raise(
    db: AsyncSession,
    rule: AlertRule,
    key: str,
    title: str,
    detail: str,
    station_id: int | None = None,
    event_id: int | None = None,
    confidence: Any = None,
) -> bool:
    """Insert once per dedupe key; safe when two evaluators run at the same time."""
    stmt = (
        pg_insert(Alert)
        .values(
            rule_id=rule.id,
            dedupe_key=key,
            type=rule.kind,
            severity=rule.severity,
            station_id=station_id,
            event_id=event_id,
            confidence=confidence,
            title=title,
            detail=detail,
            status="open",
            created_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(Alert.id)
    )
    alert_id = (await db.execute(stmt)).scalar_one_or_none()
    if alert_id is None:
        return False
    bus.publish("alert", {"alert_id": alert_id, "severity": rule.severity, "title": title, "station_id": station_id})
    return True


def _resolve(a: Alert, now: Any) -> None:
    a.status, a.resolved_at = "resolved", now
    bus.publish("alert_update", {"alert_id": a.id, "status": "resolved"})


async def _state_duration(
    db: AsyncSession, rule: AlertRule, stations: dict[int, Station], lives: dict[int, StationLive], shift: ShiftWindow
) -> int:
    """A station stuck in one state too long. Break time does not count toward the duration."""
    c, now, n = rule.condition, utcnow(), 0
    col_state, col_since = (
        ("machine_state", "machine_since") if c["event_type"] == "machine_state" else ("worker_state", "worker_since")
    )
    if not shift.in_break(now):
        for sid, lv in lives.items():
            state, since = getattr(lv, col_state), getattr(lv, col_since)
            if sid not in stations or state != c["state"] or since is None or lv.worker_state == "break":
                continue
            if since >= shift.start:
                mins = shift.worked_minutes(now) - shift.worked_minutes(since)
            else:
                mins = (now - since).total_seconds() / 60
            if mins >= float(c["min_minutes"]):
                station = stations[sid]
                key = f"r{rule.id}:s{sid}:{since.isoformat()}"
                n += await _raise(db, rule, key, f"{rule.name} · {int(mins)} min", f"{station.code} · {station.name}", sid)
    open_rows = (await db.execute(select(Alert).where(Alert.rule_id == rule.id, Alert.status != "resolved"))).scalars()
    for a in open_rows:  # the episode ended (state changed), so its alert resolves
        lv = lives.get(a.station_id or -1)
        since = getattr(lv, col_since) if lv is not None else None
        still = (
            lv is not None
            and lv.worker_state != "break"
            and getattr(lv, col_state) == c["state"]
            and since is not None
            and a.dedupe_key == f"r{rule.id}:s{a.station_id}:{since.isoformat()}"
        )
        if not still:
            _resolve(a, now)
    return n


async def _events(db: AsyncSession, rule: AlertRule, stations: dict[int, Station]) -> int:
    c, n = rule.condition, 0
    since = utcnow() - timedelta(minutes=float(c.get("lookback_minutes", 30)))
    q = select(Event).where(
        Event.event_type == c["event_type"],
        Event.state == c["state"],
        Event.start_time >= since,
        Event.review_status == "pending",
        Event.station_id.in_(list(stations)),
    )
    for e in (await db.execute(q)).scalars():
        conf = f" · confidence {float(e.confidence):.2f}" if e.confidence is not None else ""
        detail = f"{stations[e.station_id].code}{conf} · needs review"
        n += await _raise(db, rule, f"r{rule.id}:e{e.id}", rule.name, detail, e.station_id, e.id, e.confidence)
    return n


async def _device_offline(db: AsyncSession, rule: AlertRule) -> int:
    now, n = utcnow(), 0
    cutoff = now - timedelta(minutes=float(rule.condition.get("after_minutes", 3)))
    offline: set[int] = set()
    for d in (await db.execute(select(Device).where(Device.is_active, Device.last_seen_at.is_not(None)))).scalars():
        if d.last_seen_at < cutoff:
            offline.add(d.id)
            title = f"{d.kind.replace('_', ' ').capitalize()} offline"
            key = f"r{rule.id}:d{d.id}:{d.last_seen_at.isoformat()}"
            n += await _raise(db, rule, key, title, f"{d.code} · not reporting", d.station_id)
    for a in (await db.execute(select(Alert).where(Alert.rule_id == rule.id, Alert.status != "resolved"))).scalars():
        device_id = int(a.dedupe_key.split(":")[1][1:])
        if device_id not in offline:
            _resolve(a, now)
    return n


async def evaluate_rules(db: AsyncSession) -> int:
    """Run every enabled rule once. Idempotent: an episode raises at most one alert."""
    factory = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one_or_none()
    if factory is None:
        return 0
    shift = await current_shift(db, factory)
    stations = {s.id: s for s in (await db.execute(select(Station).where(Station.status != "inactive"))).scalars()}
    lives = {lv.station_id: lv for lv in (await db.execute(select(StationLive))).scalars()}
    created = 0
    for rule in (await db.execute(select(AlertRule).where(AlertRule.is_enabled))).scalars():
        try:
            if rule.kind == "state_duration":
                created += await _state_duration(db, rule, stations, lives, shift)
            elif rule.kind == "event":
                created += await _events(db, rule, stations)
            elif rule.kind == "device_offline":
                created += await _device_offline(db, rule)
        except (KeyError, ValueError, TypeError, IndexError):
            log.exception("alert rule %s has a bad condition; skipped", rule.id)
    await db.commit()
    return created
