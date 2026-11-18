"""Factory setup: structure, admin-editable lists, machines, workers (docs/API.md §4–§7, PRD F-POL-8).

Every list and count is data; nothing here hard-codes a factory's values.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import and_, func, inspect, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.catalog  # noqa: F401  (registers the catalog tables on Base.metadata)
from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import check_line_scope, client_ip, current_user, require_roles
from app.models import (
    Factory,
    Floor,
    Line,
    Machine,
    MachineAssignment,
    Operation,
    Product,
    ReasonCode,
    Station,
    User,
    Worker,
    WorkerAssignment,
)
from app.models.catalog import MachineBrand, MachineType

router = APIRouter(tags=["setup"])

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None
CardId = Annotated[str, StringConstraints(strip_whitespace=True, max_length=64, pattern=r"^[A-Za-z0-9-]*$")] | None
MachineStatus = Literal["active", "maintenance", "inactive"]


def _tz(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown time zone. Use an IANA name such as Asia/Dhaka.") from None
    return v


TimeZone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64), AfterValidator(_tz)]


def out(obj: Any) -> dict[str, Any]:
    """All mapped columns of a row (callers must never pass a User: it has password_hash)."""
    return {a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs}


async def flush(db: AsyncSession) -> None:
    """Flush; a unique-constraint violation becomes 409 DUPLICATE."""
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        if (getattr(e.orig, "sqlstate", None) or getattr(e.orig, "pgcode", None)) == "23505":
            raise AppError(409, "DUPLICATE", "A record with this code or name already exists.") from None
        raise


async def type_codes(db: AsyncSession) -> dict[str, str]:
    """Active machine types: lower-cased code and name → code."""
    rows = (await db.execute(select(MachineType).where(MachineType.is_active))).scalars()
    return {k.lower(): t.code for t in rows for k in (t.code, t.name)}


async def brand_names(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(select(MachineBrand.name).where(MachineBrand.is_active))).scalars()
    return {n.lower(): n for n in rows}


async def place_machine(db: AsyncSession, machine_id: int, station_id: int, at: datetime) -> MachineAssignment:
    """Put a machine on a station from `at`, closing the machine's and the station's open placements."""
    either = or_(MachineAssignment.machine_id == machine_id, MachineAssignment.station_id == station_id)
    later = (
        await db.execute(
            select(MachineAssignment.id)
            .where(
                either,
                or_(
                    MachineAssignment.valid_from > at,
                    and_(
                        MachineAssignment.valid_to.is_not(None),
                        MachineAssignment.valid_from <= at,
                        MachineAssignment.valid_to > at,
                    ),
                ),
            )
            .limit(1)
        )
    ).first()
    if later:
        raise AppError(409, "ASSIGNMENT_OVERLAP", "Another placement already covers this time for this machine or station.")
    for a in (
        await db.execute(select(MachineAssignment).where(either, MachineAssignment.valid_to.is_(None)).with_for_update())
    ).scalars():
        a.valid_to = at
    ma = MachineAssignment(machine_id=machine_id, station_id=station_id, valid_from=at)
    db.add(ma)
    return ma


Check = Callable[[AsyncSession, dict[str, Any], Any], Awaitable[None]]


def _crud(
    path: str,
    model: Any,
    entity: str,
    create_in: type[BaseModel],
    patch_in: type[BaseModel],
    *,
    check: Check | None = None,
    parent: str | None = None,
    list_: bool = True,
) -> None:
    """GET list (+ `?<parent>=` filter), GET one, POST, PATCH for a simple table. `check` validates and may fill data."""
    admin = require_roles("factory_admin")

    if list_:

        @router.get(path)
        async def _list(
            request: Request,
            limit: int = Query(500, ge=1, le=2000),
            db: AsyncSession = Depends(get_session),
            _: User = Depends(current_user),
        ):
            stmt = select(model).order_by(model.id).limit(limit)
            if parent and (v := request.query_params.get(parent)) is not None:
                numeric = model.__table__.c[parent].type.python_type is int
                if numeric and not v.isdigit():
                    raise AppError(400, "VALIDATION_ERROR", f"{parent} must be a number.")
                stmt = stmt.where(getattr(model, parent) == (int(v) if numeric else v))
            return ok([out(r) for r in (await db.execute(stmt)).scalars()])

        @router.get(path + "/{item_id}")
        async def _one(item_id: int, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
            obj = await db.get(model, item_id)
            if obj is None:
                raise not_found(entity.capitalize())
            return ok(out(obj))

    @router.post(path, status_code=201)
    async def _create(body: create_in, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin)):
        data = body.model_dump(exclude_none=True)
        if check:
            await check(db, data, None)
        obj = model(**data)
        db.add(obj)
        await flush(db)
        audit(db, user.id, f"{entity}.create", entity, obj.id, body.model_dump(mode="json"), client_ip(request))
        await db.commit()
        return ok(out(obj))

    @router.patch(path + "/{item_id}")
    async def _patch(
        item_id: int,
        body: patch_in,
        request: Request,
        db: AsyncSession = Depends(get_session),
        user: User = Depends(admin),
    ):
        obj = await db.get(model, item_id)
        if obj is None:
            raise not_found(entity.capitalize())
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            if v is None and not model.__table__.c[k].nullable:
                raise AppError(400, "VALIDATION_ERROR", f"{k} cannot be empty.")
        if check:
            await check(db, data, obj)
        for k, v in data.items():
            old = getattr(obj, k)
            setattr(obj, k, {**old, **v} if isinstance(old, dict) and isinstance(v, dict) else v)
        await flush(db)
        audit(
            db, user.id, f"{entity}.update", entity, obj.id, body.model_dump(mode="json", exclude_unset=True), client_ip(request)
        )
        await db.commit()
        return ok(out(obj))


async def _exists(db: AsyncSession, model: Any, id_: int | None, what: str) -> Any:
    obj = None if id_ is None else await db.get(model, id_)
    if obj is None:
        raise not_found(what)
    return obj


# ---------- structure ----------
class FactorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_tap_enabled: bool | None = None
    face_blur: bool | None = None


class FactoryIn(BaseModel):
    code: Code
    name: Name
    timezone: TimeZone = "Asia/Dhaka"
    settings: FactorySettings = FactorySettings()


class FactoryPatch(BaseModel):
    name: Name | None = None
    timezone: TimeZone | None = None
    settings: FactorySettings | None = None


class FloorIn(BaseModel):
    factory_id: int
    code: Code
    name: Name


class FloorPatch(BaseModel):
    name: Name | None = None


class LineIn(BaseModel):
    floor_id: int
    code: Code
    name: Name


class LinePatch(BaseModel):
    name: Name | None = None
    is_active: bool | None = None


class StationIn(BaseModel):
    line_id: int
    code: Code
    name: OptName = None
    position: int | None = Field(default=None, ge=0, le=100000)


class StationPatch(BaseModel):
    name: Name | None = None
    status: MachineStatus | None = None
    position: int | None = Field(default=None, ge=0, le=100000)


async def _floor_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is None:
        await _exists(db, Factory, data["factory_id"], "Factory")


async def _line_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is None:
        await _exists(db, Floor, data["floor_id"], "Floor")


async def _station_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is not None:
        return
    await _exists(db, Line, data["line_id"], "Line")
    data.setdefault("name", data["code"])
    if "position" not in data:
        last = await db.execute(select(func.coalesce(func.max(Station.position), 0)).where(Station.line_id == data["line_id"]))
        data["position"] = last.scalar_one() + 1


_crud("/factories", Factory, "factory", FactoryIn, FactoryPatch)
_crud("/floors", Floor, "floor", FloorIn, FloorPatch, check=_floor_check, parent="factory_id")
_crud("/lines", Line, "line", LineIn, LinePatch, check=_line_check, parent="floor_id")
_crud("/stations", Station, "station", StationIn, StationPatch, check=_station_check, parent="line_id")


# ---------- lists ----------
class MachineTypeIn(BaseModel):
    code: Code
    name: Name
    name_bn: OptName = None


class MachineTypePatch(BaseModel):
    name: Name | None = None
    name_bn: OptName = None
    is_active: bool | None = None


class BrandIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class BrandPatch(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    is_active: bool | None = None


async def _brand_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is not None and data.get("name") and data["name"] != obj.name:  # machines store the brand by name
        await db.execute(update(Machine).where(Machine.brand == obj.name).values(brand=data["name"]))


class ReasonIn(BaseModel):
    category: Literal["downtime", "pause", "reject"]
    code: Code
    name: Name
    name_bn: OptName = None


class ReasonPatch(BaseModel):
    name: Name | None = None
    name_bn: OptName = None
    is_active: bool | None = None


class ProductIn(BaseModel):
    code: Code
    name: Name


class ProductPatch(BaseModel):
    name: Name | None = None


Smv = Annotated[Decimal, Field(gt=0, le=999, max_digits=6, decimal_places=3)]
Group = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8, pattern=r"^[A-Za-z0-9]+$")]


class OperationIn(BaseModel):
    product_id: int
    code: Code
    name: Name
    name_bn: OptName = None
    smv: Smv
    difficulty_group: Group | None = None


class OperationPatch(BaseModel):
    name: Name | None = None
    name_bn: OptName = None
    smv: Smv | None = None
    difficulty_group: Group | None = None


async def _operation_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is None:
        await _exists(db, Product, data["product_id"], "Product")


_crud("/catalog/machine-types", MachineType, "machine_type", MachineTypeIn, MachineTypePatch)
_crud("/catalog/machine-brands", MachineBrand, "machine_brand", BrandIn, BrandPatch, check=_brand_check)
_crud("/catalog/reason-codes", ReasonCode, "reason_code", ReasonIn, ReasonPatch, parent="category")
_crud("/products", Product, "product", ProductIn, ProductPatch)
_crud("/operations", Operation, "operation", OperationIn, OperationPatch, check=_operation_check, parent="product_id")


# ---------- machines ----------
class MachineIn(BaseModel):
    factory_id: int
    asset_code: Code
    machine_type: Name
    brand: Name
    model: OptName = None
    status: MachineStatus = "active"


class MachinePatch(BaseModel):
    machine_type: Name | None = None
    brand: Name | None = None
    model: OptName = None
    status: MachineStatus | None = None


async def _machine_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is None:
        await _exists(db, Factory, data["factory_id"], "Factory")
    if data.get("machine_type"):
        code = (await type_codes(db)).get(data["machine_type"].lower())
        if code is None:
            raise AppError(422, "UNKNOWN_LIST_VALUE", f"'{data['machine_type']}' is not an active machine type. Add it in Lists.")
        data["machine_type"] = code
    if data.get("brand"):
        name = (await brand_names(db)).get(data["brand"].lower())
        if name is None:
            raise AppError(422, "UNKNOWN_LIST_VALUE", f"'{data['brand']}' is not an active machine brand. Add it in Lists.")
        data["brand"] = name


_crud("/machines", Machine, "machine", MachineIn, MachinePatch, check=_machine_check, list_=False)


@router.get("/machines")
async def machines(
    line_id: int | None = None,
    status: MachineStatus | None = None,
    q: str | None = Query(None, max_length=60),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_session),
    _: User = Depends(current_user),
):
    cur = (
        select(MachineAssignment.machine_id, MachineAssignment.station_id).where(MachineAssignment.valid_to.is_(None)).subquery()
    )
    stmt = (
        select(Machine, Station)
        .outerjoin(cur, cur.c.machine_id == Machine.id)
        .outerjoin(Station, Station.id == cur.c.station_id)
        .order_by(Machine.asset_code)
        .limit(limit)
    )
    if line_id is not None:
        stmt = stmt.where(Station.line_id == line_id)
    if status:
        stmt = stmt.where(Machine.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Machine.asset_code.ilike(like), Machine.brand.ilike(like), Machine.model.ilike(like)))
    rows = (await db.execute(stmt)).all()
    return ok([{**out(m), "station": {"id": s.id, "code": s.code, "line_id": s.line_id} if s else None} for m, s in rows])


@router.get("/machines/{machine_id}")
async def machine(machine_id: int, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    return ok(out(await _exists(db, Machine, machine_id, "Machine")))


class PlaceIn(BaseModel):
    station_id: int
    valid_from: datetime | None = None

    @field_validator("valid_from")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("valid_from must include a time zone")
        return v


@router.post("/machines/{machine_id}/assign", status_code=201)
async def assign_machine(
    machine_id: int,
    body: PlaceIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    await _exists(db, Machine, machine_id, "Machine")
    await _exists(db, Station, body.station_id, "Station")
    at = body.valid_from or utcnow()
    ma = await place_machine(db, machine_id, body.station_id, at)
    await db.flush()
    audit(db, user.id, "machine.assign", "machine", machine_id, body.model_dump(mode="json"), client_ip(request))
    await db.commit()
    return ok({"id": ma.id, "machine_id": machine_id, "station_id": body.station_id, "valid_from": at.isoformat()})


# ---------- workers and assignments ----------
def _blank_to_none(v: str | None) -> str | None:
    return v or None


class WorkerIn(BaseModel):
    factory_id: int
    employee_code: Code
    full_name: Name
    full_name_bn: OptName = None
    rfid_card_id: Annotated[CardId, AfterValidator(_blank_to_none)] = None


class WorkerPatch(BaseModel):
    full_name: Name | None = None
    full_name_bn: OptName = None
    rfid_card_id: Annotated[CardId, AfterValidator(_blank_to_none)] = None
    is_active: bool | None = None


async def _worker_check(db: AsyncSession, data: dict[str, Any], obj: Any) -> None:
    if obj is None:
        await _exists(db, Factory, data["factory_id"], "Factory")


# GET /workers (list) lives in org.py; detail, create and edit live here.
_crud("/workers", Worker, "worker", WorkerIn, WorkerPatch, check=_worker_check, list_=False)


@router.get("/workers/{worker_id}")
async def worker(worker_id: int, db: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    return ok(out(await _exists(db, Worker, worker_id, "Worker")))


@router.get("/assignments")
async def assignments(
    station_id: int | None = None,
    worker_id: int | None = None,
    active: bool = False,
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_session),
    _: User = Depends(current_user),
):
    stmt = (
        select(WorkerAssignment, Worker, Station, Operation)
        .join(Worker, Worker.id == WorkerAssignment.worker_id)
        .join(Station, Station.id == WorkerAssignment.station_id)
        .join(Operation, Operation.id == WorkerAssignment.operation_id)
        .order_by(WorkerAssignment.valid_from.desc())
        .limit(limit)
    )
    if station_id is not None:
        stmt = stmt.where(WorkerAssignment.station_id == station_id)
    if worker_id is not None:
        stmt = stmt.where(WorkerAssignment.worker_id == worker_id)
    if active:
        stmt = stmt.where(WorkerAssignment.valid_to.is_(None))
    rows = (await db.execute(stmt)).all()
    return ok(
        [
            {
                **out(a),
                "worker": {"id": w.id, "employee_code": w.employee_code, "full_name": w.full_name},
                "station": {"id": s.id, "code": s.code, "line_id": s.line_id},
                "operation": {"id": o.id, "code": o.code, "name": o.name},
            }
            for a, w, s, o in rows
        ]
    )


@router.post("/assignments/{assignment_id}/end")
async def end_assignment(
    assignment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin", "supervisor")),
):
    a = await _exists(db, WorkerAssignment, assignment_id, "Assignment")
    station = await db.get(Station, a.station_id)
    check_line_scope(user, station.line_id if station else -1)
    if a.valid_to is not None:
        raise AppError(409, "ALREADY_ENDED", "This assignment has already ended.")
    a.valid_to = max(utcnow(), a.valid_from)
    audit(db, user.id, "assignment.end", "assignment", a.id, None, client_ip(request))
    await db.commit()
    return ok(out(a))
