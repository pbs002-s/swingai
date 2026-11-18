"""Needle lots and break statistics (docs/API.md §14, PRD F-NDL-4/5)."""

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import client_ip, require_roles
from app.models import NeedleBatch, NeedleEvent, NeedleIssue, NeedleSupplier, User

router = APIRouter(tags=["needles"])
ALERT_PER_1000H = 25.0  # ponytail: move into the thresholds policy when the needles UI edits it
MIN_ISSUED, MIN_HOURS = 10, 50.0


def _pattern(issued: int, hours: float, rate: float, machines: int, workers: int) -> str:
    if issued < MIN_ISSUED or hours < MIN_HOURS:
        return "too_little_use"
    if rate < ALERT_PER_1000H:
        return "normal"
    if machines >= 3 and workers >= 3:
        return "batch"
    return "machine" if machines < 3 else "worker"


@router.get("/needles/stats")
async def needle_stats(
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("factory_admin", "quality", "maintenance", "management")),
):
    now = utcnow()
    batches = (await db.execute(select(NeedleBatch, NeedleSupplier).join(NeedleSupplier))).all()
    issues = list((await db.execute(select(NeedleIssue))).scalars())
    events = list(
        (
            await db.execute(select(NeedleEvent).where(NeedleEvent.status == "confirmed", NeedleEvent.type == "needle_break"))
        ).scalars()
    )
    by_issue = {i.id: i for i in issues}
    issued: dict[int, int] = defaultdict(int)
    hours: dict[int, float] = defaultdict(float)
    for i in issues:
        issued[i.batch_id] += 1
        # ponytail: installed time stands in for motor-running time until machine run minutes are aggregated
        hours[i.batch_id] += ((i.removed_at or now) - i.installed_at).total_seconds() / 3600
    breaks: dict[int, int] = defaultdict(int)
    machines: dict[int, set[int]] = defaultdict(set)
    workers: dict[int, set[int]] = defaultdict(set)
    for ev in events:
        issue = by_issue.get(ev.needle_issue_id)
        if issue is None:
            continue
        breaks[issue.batch_id] += 1
        machines[issue.batch_id].add(issue.machine_id)
        if ev.worker_id:
            workers[issue.batch_id].add(ev.worker_id)
    out: list[dict[str, Any]] = []
    for b, sup in batches:
        h, n = hours[b.id], breaks[b.id]
        rate = n / h * 1000 if h else 0.0
        out.append(
            {
                "batch_id": b.id,
                "lot_no": b.lot_no,
                "supplier": sup.name,
                "model": b.model,
                "status": b.status,
                "issued": issued[b.id],
                "confirmed_breaks": n,
                "running_hours": round(h, 1),
                "break_rate_pct": round(n / issued[b.id] * 100, 1) if issued[b.id] else 0.0,
                "breaks_per_1000h": round(rate, 1),
                "machines": len(machines[b.id]),
                "workers": len(workers[b.id]),
                "pattern": _pattern(issued[b.id], h, rate, len(machines[b.id]), len(workers[b.id])),
            }
        )
    out.sort(key=lambda x: x["breaks_per_1000h"], reverse=True)
    return ok(out, {"alert_per_1000h": ALERT_PER_1000H, "min_issued": MIN_ISSUED, "min_hours": MIN_HOURS})


@router.post("/needle-batches/{batch_id}/quarantine")
async def quarantine(
    batch_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin", "quality", "maintenance")),
):
    b = await db.get(NeedleBatch, batch_id)
    if b is None:
        raise not_found("Needle lot")
    if b.status == "quarantined":
        raise AppError(409, "ALREADY_QUARANTINED", "This lot is already quarantined.")
    b.status = "quarantined"
    audit(db, user.id, "needle_batch.quarantine", "needle_batch", b.id, ip=client_ip(request))
    await db.commit()
    return ok({"batch_id": b.id, "status": b.status})
