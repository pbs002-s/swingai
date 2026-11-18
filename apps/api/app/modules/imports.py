"""CSV import with a dry-run preview (docs/IMPORT_TEMPLATES.md).

Every row runs through the same code in preview and commit; preview rolls the transaction back,
commit writes all valid rows in one transaction. Rows with errors are reported and skipped.
"""

import csv
import io
import itertools
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, ok
from app.core.security import client_ip, require_roles
from app.models import (
    Event,
    Factory,
    Floor,
    Line,
    Machine,
    MachineAssignment,
    NeedleBatch,
    NeedleSupplier,
    Operation,
    Product,
    Station,
    User,
    Worker,
    WorkerAssignment,
)
from app.modules.ingest import review_status
from app.modules.setup import brand_names, place_machine, type_codes

router = APIRouter(tags=["setup"])

MAX_ROWS = 10_000
MAX_BYTES = 8 * 1024 * 1024
MAX_ERRORS_SHOWN = 1000
CODE_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
ATTENDANCE_NS = uuid.UUID("6f1c3f0e-4d0a-4b7e-9a51-2d3c0b8e7a11")

Kind = Literal["org", "machines", "workers", "operations", "needle-batches", "attendance"]
Row = dict[str, str]
RowFn = Callable[[Row], Awaitable[str]]  # returns "create" | "update"


class RowError(Exception):
    def __init__(self, column: str, message: str):
        super().__init__(message)
        self.column, self.message = column, message


def text(r: Row, col: str, max_len: int = 120, required: bool = True) -> str | None:
    v = r.get(col, "")
    if not v:
        if required:
            raise RowError(col, "Required.")
        return None
    if len(v) > max_len:
        raise RowError(col, f"At most {max_len} characters.")
    return v


def code(r: Row, col: str, required: bool = True) -> str | None:
    v = text(r, col, 32, required)
    if v is not None and not CODE_RE.match(v):
        raise RowError(col, "Use letters, digits, '.', '_' or '-' only.")
    return v


def day(r: Row, col: str, required: bool = True) -> date | None:
    v = text(r, col, 10, required)
    try:
        return None if v is None else date.fromisoformat(v)
    except ValueError:
        raise RowError(col, "Use YYYY-MM-DD.") from None


def whole(r: Row, col: str, lo: int, hi: int) -> int:
    v = text(r, col, 10)
    if not v or not v.isdigit() or not lo <= int(v) <= hi:
        raise RowError(col, f"Whole number from {lo} to {hi}.")
    return int(v)


def choice(r: Row, col: str, allowed: tuple[str, ...]) -> str | None:
    v = text(r, col, 32, required=False)
    if v is not None and v not in allowed:
        raise RowError(col, f"Use one of: {', '.join(allowed)}.")
    return v


async def _org(db: AsyncSession) -> RowFn:
    factories = {f.code: f for f in (await db.execute(select(Factory))).scalars()}
    floors = {(f.factory_id, f.code): f for f in (await db.execute(select(Floor))).scalars()}
    lines = {(ln.floor_id, ln.code): ln for ln in (await db.execute(select(Line))).scalars()}
    stations = {s.code: s for s in (await db.execute(select(Station))).scalars()}
    pos = dict((await db.execute(select(Station.line_id, func.max(Station.position)).group_by(Station.line_id))).all())

    async def row(r: Row) -> str:
        factory = factories.get(code(r, "factory_code") or "")
        if factory is None:
            raise RowError("factory_code", "Factory not found. Create it first.")
        fl_code, fl_name = code(r, "floor_code"), text(r, "floor_name")
        ln_code, ln_name = code(r, "line_code"), text(r, "line_name")
        st_code = code(r, "station_code") or ""
        st_name = text(r, "station_name", required=False) or st_code
        fl = floors.get((factory.id, fl_code))
        if fl is None:
            fl = floors[(factory.id, fl_code)] = Floor(factory_id=factory.id, code=fl_code, name=fl_name)
            db.add(fl)
            await db.flush()
        fl.name = fl_name
        ln = lines.get((fl.id, ln_code))
        if ln is None:
            ln = lines[(fl.id, ln_code)] = Line(floor_id=fl.id, code=ln_code, name=ln_name)
            db.add(ln)
            await db.flush()
        ln.name = ln_name
        st = stations.get(st_code)
        if st is not None:
            st.line_id, st.name = ln.id, st_name
            return "update"
        pos[ln.id] = (pos.get(ln.id) or 0) + 1
        stations[st_code] = Station(line_id=ln.id, code=st_code, name=st_name, position=pos[ln.id])
        db.add(stations[st_code])
        return "create"

    return row


async def _machines(db: AsyncSession) -> RowFn:
    factories = {f.code: f.id for f in (await db.execute(select(Factory))).scalars()}
    types, brands = await type_codes(db), await brand_names(db)
    machines = {m.asset_code: m for m in (await db.execute(select(Machine))).scalars()}
    stations = {s.code: s.id for s in (await db.execute(select(Station))).scalars()}
    q = select(MachineAssignment.machine_id, MachineAssignment.station_id).where(MachineAssignment.valid_to.is_(None))
    placed = dict((await db.execute(q)).all())
    now = utcnow()

    async def row(r: Row) -> str:
        asset = code(r, "asset_code") or ""
        factory_id = factories.get(code(r, "factory_code") or "")
        if factory_id is None:
            raise RowError("factory_code", "Factory not found.")
        mtype = types.get((text(r, "machine_type", 64) or "").lower())
        if mtype is None:
            raise RowError("machine_type", "Not an active machine type. Add it in Setup → Lists first.")
        brand = brands.get((text(r, "brand", 64) or "").lower())
        if brand is None:
            raise RowError("brand", "Not an active machine brand. Add it in Setup → Lists first.")
        model = text(r, "model", 64, required=False)
        text(r, "serial", 64, required=False)  # ponytail: validated only; add a column when maintenance needs it
        st_code = code(r, "station_code", required=False)
        station_id = stations.get(st_code) if st_code else None
        if st_code and station_id is None:
            raise RowError("station_code", "Station not found.")
        status = choice(r, "status", ("active", "maintenance", "inactive")) or "active"
        m = machines.get(asset)
        result = "update" if m else "create"
        if m is None:
            m = machines[asset] = Machine(factory_id=factory_id, asset_code=asset, machine_type=mtype, brand=brand)
            db.add(m)
            await db.flush()
        m.factory_id, m.machine_type, m.brand, m.model, m.status = factory_id, mtype, brand, model, status
        if station_id is not None and placed.get(m.id) != station_id:
            try:
                await place_machine(db, m.id, station_id, now)
            except AppError as e:
                raise RowError("station_code", f"Machine saved but not placed: {e.message}") from None
            placed[m.id] = station_id
        return result

    return row


async def _workers(db: AsyncSession) -> RowFn:
    factories = {f.code: f.id for f in (await db.execute(select(Factory))).scalars()}
    workers = {w.employee_code: w for w in (await db.execute(select(Worker))).scalars()}
    cards = {w.rfid_card_id: w.employee_code for w in workers.values() if w.rfid_card_id}
    ops = set((await db.execute(select(Operation.code))).scalars())

    async def row(r: Row) -> str:
        emp = code(r, "employee_code") or ""
        factory_id = factories.get(code(r, "factory_code") or "")
        if factory_id is None:
            raise RowError("factory_code", "Factory not found.")
        name, name_bn = text(r, "full_name"), text(r, "full_name_bn", required=False)
        card = text(r, "rfid_card_id", 64, required=False)
        if card and cards.get(card, emp) != emp:
            raise RowError("rfid_card_id", f"Card already belongs to worker {cards[card]}.")
        day(r, "joined_on", required=False)
        for part in filter(None, (text(r, "skills", 2000, required=False) or "").split(";")):
            op, _, level = part.strip().partition(":")
            if op not in ops or level not in {"1", "2", "3", "4", "5"}:
                raise RowError("skills", f"'{part}' must be operation_code:level (1–5) with a known operation.")
        # ponytail: joined_on and skills are validated but not stored until the worker-skills table lands (API.md §7).
        w = workers.get(emp)
        result = "update" if w else "create"
        if w is None:
            w = workers[emp] = Worker(factory_id=factory_id, employee_code=emp, full_name=name)
            db.add(w)
        cards.pop(w.rfid_card_id or "", None)
        w.factory_id, w.full_name, w.full_name_bn, w.rfid_card_id = factory_id, name, name_bn, card
        if card:
            cards[card] = emp
        return result

    return row


def _smv(r: Row) -> Decimal:
    try:
        v = Decimal(text(r, "smv", 12) or "")
    except InvalidOperation:
        raise RowError("smv", "Must be a number, e.g. 0.450.") from None
    if not v.is_finite() or v <= 0 or v > 999 or -v.as_tuple().exponent > 3:
        raise RowError("smv", "Must be above 0, at most 999, with up to 3 decimals.")
    return v


async def _operations(db: AsyncSession) -> RowFn:
    products = {p.code: p for p in (await db.execute(select(Product))).scalars()}
    ops = {o.code: o for o in (await db.execute(select(Operation))).scalars()}
    types = await type_codes(db)

    async def row(r: Row) -> str:
        p_code, p_name = code(r, "product_code") or "", text(r, "product_name")
        text(r, "style_no", 48, required=False)
        o_code, o_name, o_bn = (
            code(r, "operation_code") or "",
            text(r, "operation_name"),
            text(r, "operation_name_bn", required=False),
        )
        smv = _smv(r)
        if (text(r, "machine_type", 64) or "").lower() not in types:
            raise RowError("machine_type", "Not an active machine type. Add it in Setup → Lists first.")
        text(r, "count_unit", 200)
        group = text(r, "difficulty_group", 8, required=False)
        if group and not group.isalnum():
            raise RowError("difficulty_group", "Letters or digits only, e.g. A, B, C.")
        # ponytail: style_no, machine_type and count_unit are validated but not stored until Operation has those columns.
        p = products.get(p_code)
        if p is None:
            p = products[p_code] = Product(code=p_code, name=p_name)
            db.add(p)
            await db.flush()
        p.name = p_name
        o = ops.get(o_code)
        result = "update" if o else "create"
        if o is None:
            o = ops[o_code] = Operation(product_id=p.id, code=o_code, name=o_name, smv=smv)
            db.add(o)
        o.product_id, o.name, o.name_bn, o.smv = p.id, o_name, o_bn, smv
        if group:
            o.difficulty_group = group
        return result

    return row


async def _needle_batches(db: AsyncSession) -> RowFn:
    suppliers = {s.name: s for s in (await db.execute(select(NeedleSupplier))).scalars()}
    batches = {(b.supplier_id, b.lot_no): b for b in (await db.execute(select(NeedleBatch))).scalars()}

    async def row(r: Row) -> str:
        supplier = text(r, "supplier_name") or ""
        brand, system = text(r, "brand", 32), text(r, "system", 16)
        size = whole(r, "size_nm", 1, 1000)
        point = text(r, "point_type", 16, required=False)
        lot = text(r, "lot_no", 48) or ""
        received = day(r, "received_on")
        qty = whole(r, "qty_received", 1, 1_000_000)
        model = f"{brand} {system} · Nm {size}" + (f" · {point}" if point else "")
        if len(model) > 64:
            raise RowError("brand", "Brand, system and point type together are too long.")
        s = suppliers.get(supplier)
        if s is None:
            s = suppliers[supplier] = NeedleSupplier(name=supplier)
            db.add(s)
            await db.flush()
        b = batches.get((s.id, lot))
        result = "update" if b else "create"
        if b is None:
            b = batches[(s.id, lot)] = NeedleBatch(
                supplier_id=s.id, lot_no=lot, model=model, received_on=received, qty_received=qty
            )
            db.add(b)
        b.model, b.received_on, b.qty_received = model, received, qty
        return result

    return row


async def _attendance(db: AsyncSession) -> RowFn:
    workers = list((await db.execute(select(Worker))).scalars())
    by_code = {w.employee_code: w for w in workers}
    by_card = {w.rfid_card_id: w for w in workers if w.rfid_card_id}
    zones = {f.id: ZoneInfo(f.timezone) for f in (await db.execute(select(Factory))).scalars()}
    q = select(WorkerAssignment).where(WorkerAssignment.valid_to.is_(None))
    active = {a.worker_id: a for a in (await db.execute(q)).scalars()}
    seen: set[uuid.UUID] = set()

    async def row(r: Row) -> str:
        emp, card = text(r, "employee_code", 32, required=False), text(r, "card_id", 64, required=False)
        if not emp and not card:
            raise RowError("employee_code", "Fill employee_code or card_id.")
        w = by_code.get(emp or "") or by_card.get(card or "")
        if w is None:
            raise RowError("employee_code" if emp else "card_id", "Worker not found.")
        if emp and card and by_card.get(card) is not w:
            raise RowError("card_id", "Card does not belong to this employee.")
        try:
            local = datetime.strptime(text(r, "punch_time", 16) or "", "%Y-%m-%d %H:%M")
        except ValueError:
            raise RowError("punch_time", "Use YYYY-MM-DD HH:MM (factory local time).") from None
        at = local.replace(tzinfo=zones.get(w.factory_id, UTC)).astimezone(UTC)
        direction = choice(r, "direction", ("in", "out"))
        device = text(r, "device", 64, required=False)
        a = active.get(w.id)
        if a is None:
            raise RowError("employee_code", "Worker has no active station assignment; punch skipped.")
        key = uuid.uuid5(ATTENDANCE_NS, f"{w.id}|{at.isoformat()}")
        # ponytail: one indexed lookup per row; batch it if 10k-row files get slow.
        if key in seen or (await db.execute(select(Event.id).where(Event.event_uuid == key))).first():
            raise RowError("punch_time", "This punch was already imported.")
        seen.add(key)
        db.add(
            Event(
                event_uuid=key,
                event_type="rfid_tap",
                state="tap",
                station_id=a.station_id,
                worker_id=w.id,
                operation_id=a.operation_id,
                source="import",
                start_time=at,
                review_status=review_status("rfid_tap", "tap", None),
                meta={"direction": direction, "device": device},
            )
        )
        return "create"

    return row


KINDS: dict[str, tuple[set[str], set[str], Callable[[AsyncSession], Awaitable[RowFn]]]] = {
    "org": ({"factory_code", "floor_code", "floor_name", "line_code", "line_name", "station_code"}, {"station_name"}, _org),
    "machines": (
        {"asset_code", "factory_code", "machine_type", "brand"},
        {"model", "serial", "station_code", "status"},
        _machines,
    ),
    "workers": (
        {"employee_code", "factory_code", "full_name"},
        {"full_name_bn", "rfid_card_id", "joined_on", "skills"},
        _workers,
    ),
    "operations": (
        {"product_code", "product_name", "operation_code", "operation_name", "smv", "machine_type", "count_unit"},
        {"style_no", "operation_name_bn", "difficulty_group"},
        _operations,
    ),
    "needle-batches": (
        {"supplier_name", "brand", "system", "size_nm", "lot_no", "received_on", "qty_received"},
        {"point_type"},
        _needle_batches,
    ),
    "attendance": ({"punch_time"}, {"employee_code", "card_id", "direction", "device"}, _attendance),
}


def _parse(raw: bytes, kind: str) -> list[Row]:
    if len(raw) > MAX_BYTES:
        raise AppError(400, "FILE_TOO_LARGE", f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(400, "BAD_ENCODING", "The file is not UTF-8. In Excel use Save As → CSV UTF-8.") from None
    reader = csv.DictReader(io.StringIO(content))
    header = [h.strip() for h in reader.fieldnames or []]
    reader.fieldnames = header
    required, optional, _ = KINDS[kind]
    missing, unknown = sorted(required - set(header)), sorted(set(header) - required - optional)
    if missing or unknown or len(header) != len(set(header)):
        raise AppError(400, "BAD_HEADER", "The header row does not match the template.", {"missing": missing, "unknown": unknown})
    rows = list(itertools.islice(reader, MAX_ROWS + 1))
    if len(rows) > MAX_ROWS:
        raise AppError(400, "TOO_MANY_ROWS", f"At most {MAX_ROWS:,} rows per file.")
    if not rows:
        raise AppError(400, "EMPTY_FILE", "The file has a header but no rows.")
    return rows


@router.post("/import/{kind}")
async def import_csv(
    kind: Kind,
    request: Request,
    file: UploadFile = File(...),
    commit: bool = False,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    rows = _parse(await file.read(MAX_BYTES + 1), kind)
    handle = await KINDS[kind][2](db)
    counts = {"create": 0, "update": 0}
    errors: list[dict[str, object]] = []
    for n, raw in enumerate(rows, start=2):  # row 1 is the header
        if None in raw:
            errors.append({"row": n, "column": "", "message": "More values than header columns."})
            continue
        try:
            counts[await handle({k: (v or "").strip() for k, v in raw.items()})] += 1
        except RowError as e:
            errors.append({"row": n, "column": e.column, "message": e.message})
    result = {"kind": kind, **counts, "errors": errors[:MAX_ERRORS_SHOWN], "error_count": len(errors), "committed": commit}
    if commit:
        detail = {"file": (file.filename or "")[:120], **counts, "errors": len(errors)}
        audit(db, user.id, f"import.{kind}", "import", None, detail, client_ip(request))
        await db.commit()
    else:
        await db.rollback()
    return ok(result)
