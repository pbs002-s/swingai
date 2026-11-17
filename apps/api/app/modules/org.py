"""Factory structure, workers, assignments and manual production (docs/API.md §4, §7, §12)."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import check_line_scope, client_ip, current_user, require_roles
from app.models import (
    Factory,
    Floor,
    Line,
    Operation,
    ProductionEntry,
    Station,
    User,
    Worker,
    WorkerAssignment,
)

router = APIRouter(tags=["org"])


@router.get("/org/tree")
async def org_tree(db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    counts = dict(
        (
            await db.execute(select(Station.line_id, func.count()).where(Station.status != "inactive").group_by(Station.line_id))
        ).all()
    )
    factories = list((await db.execute(select(Factory).order_by(Factory.id))).scalars())
    floors = list((await db.execute(select(Floor).order_by(Floor.id))).scalars())
    lines = list((await db.execute(select(Line).where(Line.is_active).order_by(Line.id))).scalars())
    tree: list[dict[str, Any]] = []
    for f in factories:
        fl_out = []
        for fl in (x for x in floors if x.factory_id == f.id):
            fl_out.append(
                {
                    "id": fl.id,
                    "code": fl.code,
                    "name": fl.name,
                    "lines": [
                        {"id": ln.id, "code": ln.code, "name": ln.name, "stations": counts.get(ln.id, 0)}
                        for ln in lines
                        if ln.floor_id == fl.id
                    ],
                }
            )
        tree.append({"id": f.id, "code": f.code, "name": f.name, "timezone": f.timezone, "floors": fl_out})
    return ok(tree)


class BulkStationsIn(BaseModel):
    line_id: int
    prefix: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9-]+$")
    start: int = Field(ge=1, le=9999)
    count: int = Field(ge=1, le=500)
    pad: int = Field(default=3, ge=1, le=4)


@router.post("/stations/bulk", status_code=201)
async def bulk_stations(
    body: BulkStationsIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    if await db.get(Line, body.line_id) is None:
        raise not_found("Line")
    codes = [f"{body.prefix}{n:0{body.pad}d}" for n in range(body.start, body.start + body.count)]
    taken = set((await db.execute(select(Station.code).where(Station.code.in_(codes)))).scalars())
    if taken:
        raise AppError(409, "STATION_CODE_TAKEN", "Some station codes already exist.", {"codes": sorted(taken)[:20]})
    pos = (
        await db.execute(select(func.coalesce(func.max(Station.position), 0)).where(Station.line_id == body.line_id))
    ).scalar_one()
    db.add_all(Station(line_id=body.line_id, code=c, name=c, position=pos + i + 1) for i, c in enumerate(codes))
    audit(db, user.id, "station.bulk_create", "line", body.line_id, {"first": codes[0], "count": len(codes)}, client_ip(request))
    await db.commit()
    return ok({"created": len(codes), "first": codes[0], "last": codes[-1]})


@router.get("/workers")
async def workers(
    q: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)
):
    stmt = select(Worker).where(Worker.is_active).order_by(Worker.employee_code).limit(max(1, min(limit, 200)))
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(Worker.full_name.ilike(like), Worker.employee_code.ilike(like)))
    rows = (await db.execute(stmt)).scalars()
    return ok(
        [{"id": w.id, "employee_code": w.employee_code, "full_name": w.full_name, "full_name_bn": w.full_name_bn} for w in rows]
    )


class AssignmentIn(BaseModel):
    worker_id: int
    station_id: int
    operation_id: int
    valid_from: datetime | None = None

    @field_validator("valid_from")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("valid_from must include a time zone")
        return v


@router.post("/assignments", status_code=201)
async def assign(
    body: AssignmentIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin", "supervisor")),
):
    """Put a worker on a station from `valid_from`; closes the worker's and the station's open assignments."""
    at = body.valid_from or utcnow()
    worker = await db.get(Worker, body.worker_id)
    if worker is None or not worker.is_active:
        raise AppError(422, "WORKER_INACTIVE", "That worker is not active.")
    station = await db.get(Station, body.station_id)
    if station is None or await db.get(Operation, body.operation_id) is None:
        raise not_found("Station or operation")
    check_line_scope(user, station.line_id)
    later = (
        await db.execute(
            select(WorkerAssignment.id)
            .where(
                or_(WorkerAssignment.worker_id == body.worker_id, WorkerAssignment.station_id == body.station_id),
                or_(
                    WorkerAssignment.valid_from > at,
                    and_(
                        WorkerAssignment.valid_to.is_not(None), WorkerAssignment.valid_from <= at, WorkerAssignment.valid_to > at
                    ),
                ),
            )
            .limit(1)
        )
    ).first()
    if later:
        raise AppError(409, "ASSIGNMENT_OVERLAP", "Another assignment already covers this time for this worker or station.")
    open_rows = (
        await db.execute(
            select(WorkerAssignment)
            .where(
                or_(WorkerAssignment.worker_id == body.worker_id, WorkerAssignment.station_id == body.station_id),
                WorkerAssignment.valid_to.is_(None),
            )
            .with_for_update()
        )
    ).scalars()
    for a in open_rows:
        a.valid_to = at
    wa = WorkerAssignment(
        worker_id=body.worker_id, station_id=body.station_id, operation_id=body.operation_id, valid_from=at, assigned_by=user.id
    )
    db.add(wa)
    await db.flush()
    audit(db, user.id, "assignment.create", "assignment", wa.id, body.model_dump(mode="json"), client_ip(request))
    await db.commit()
    return ok({"id": wa.id, "valid_from": at.isoformat()})


class ProductionIn(BaseModel):
    worker_id: int | None = None
    station_id: int
    operation_id: int
    period_start: datetime
    period_end: datetime
    qty_accepted: int = Field(ge=0, le=10000)
    qty_rework: int = Field(default=0, ge=0, le=10000)
    qty_rejected: int = Field(default=0, ge=0, le=10000)


@router.post("/production-entries", status_code=201)
async def production_entry(
    body: ProductionIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin", "supervisor")),
):
    if body.period_start.tzinfo is None or body.period_end <= body.period_start:
        raise AppError(400, "VALIDATION_ERROR", "Period must have a time zone and end after it starts.")
    if body.period_end - body.period_start > timedelta(hours=12):
        raise AppError(400, "VALIDATION_ERROR", "One entry can cover at most 12 hours.")
    station = await db.get(Station, body.station_id)
    if station is None or await db.get(Operation, body.operation_id) is None:
        raise not_found("Station or operation")
    if body.worker_id is not None and await db.get(Worker, body.worker_id) is None:
        raise not_found("Worker")
    check_line_scope(user, station.line_id)
    pe = ProductionEntry(**body.model_dump(), source="manual", status="confirmed", confirmed_by=user.id)
    db.add(pe)
    await db.flush()
    audit(db, user.id, "production.create", "production_entry", pe.id, body.model_dump(mode="json"), client_ip(request))
    await db.commit()
    return ok({"id": pe.id})
