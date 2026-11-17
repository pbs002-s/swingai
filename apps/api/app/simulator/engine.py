"""Factory simulator for demos: backfills today's shift, then keeps the floor moving in real time.

It feeds the same ingest code a real edge box uses, so every screen, alert and review works on it.
"""

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import utcnow
from app.models import (
    Device,
    Event,
    Factory,
    Operation,
    Policy,
    PolicyVersion,
    ProductionEntry,
    Station,
    StationLive,
    WorkerAssignment,
)
from app.modules.ingest import EventIn, ingest_batch, review_status
from app.modules.shift import DEFAULT_SHIFT, ShiftWindow, current_shift

log = logging.getLogger("stitchsense.simulator")
TICK_S = 3.0
OFFLINE_CAMERAS = 2  # these cameras stop reporting, so their stations show "no data"

# per-minute transition rates from each worker state
RATES: dict[str, list[tuple[str, float]]] = {
    "working": [("idle", 0.025), ("away", 0.006), ("phone_use", 0.0012), ("down", 0.0025)],
    "idle": [("working", 0.35)],
    "away": [("working", 0.12)],
    "phone_use": [("working", 0.45)],
    "down": [("working", 0.07)],
}


@dataclass
class Sim:
    station: Station
    smv: float
    worker_id: int | None
    operation_id: int | None
    state: str = "working"
    produced: float = 0.0
    hour_units: dict[datetime, float] = field(default_factory=dict)


def _ev(sim: Sim, kind: str, state: str, at: datetime, conf: float | None = None) -> EventIn:
    return EventIn(
        event_uuid=uuid.uuid4(),
        event_type=kind,
        state=state,
        station_code=sim.station.code,
        start_time=at,
        confidence=Decimal(f"{conf:.3f}") if conf is not None else None,
        model_version="sim-1.0" if kind == "worker_state" else None,
    )


def _transition(sim: Sim, new: str, at: datetime, rng: random.Random) -> list[EventIn]:
    sim.state = new
    worker = "idle" if new == "down" else new
    conf = rng.uniform(0.62, 0.95) if new == "phone_use" else rng.uniform(0.8, 0.99)
    machine = "running" if new == "working" else "stopped"
    return [_ev(sim, "worker_state", worker, at, conf), _ev(sim, "machine_state", machine, at)]


def _step(sim: Sim, at: datetime, minutes: float, shift: ShiftWindow, rng: random.Random) -> list[EventIn]:
    """Advance one station by `minutes`. Returns the transitions to ingest."""
    if sim.state == "off":
        return []
    if shift.in_break(at):
        return _transition(sim, "break", at, rng) if sim.state != "break" else []
    if sim.state == "break":
        return _transition(sim, "working", at, rng)
    if sim.state == "working":
        units = minutes / sim.smv * rng.uniform(0.62, 0.86)
        hour = at.replace(minute=0, second=0, microsecond=0)
        sim.hour_units[hour] = sim.hour_units.get(hour, 0.0) + units
    for new, rate in RATES.get(sim.state, []):
        if rng.random() < rate * minutes:
            return _transition(sim, new, at, rng)
    return []


async def ensure_demo_shift(db: AsyncSession, factory: Factory) -> bool:
    """Demo only: if the clock is outside the shift, add a shift policy version that runs from 4 hours ago.

    Lets the simulator show a live floor at any hour. Uses a new policy version, so history stays intact.
    """
    shift, now = await current_shift(db, factory), utcnow()
    if shift.start <= now < shift.end:
        return False
    local = now.astimezone(shift.tz).replace(minute=0, second=0, microsecond=0)
    start = local - timedelta(hours=4)
    fmt = "%H:%M"
    body = {
        **DEFAULT_SHIFT,
        "start": start.strftime(fmt),
        "end": (start + timedelta(hours=9)).strftime(fmt),
        "crosses_midnight": (start + timedelta(hours=9)).date() != start.date(),
        "breaks": [{"start": (start + timedelta(hours=5)).strftime(fmt), "end": (start + timedelta(hours=6)).strftime(fmt)}],
    }
    policy = (await db.execute(select(Policy).where(Policy.factory_id == factory.id, Policy.kind == "shift"))).scalar_one()
    versions = list((await db.execute(select(PolicyVersion).where(PolicyVersion.policy_id == policy.id))).scalars())
    for v in versions:
        if v.effective_to is None:
            v.effective_to = now
    db.add(
        PolicyVersion(
            policy_id=policy.id, version=max((v.version for v in versions), default=0) + 1, body=body, effective_from=now
        )
    )
    await db.commit()
    log.info("demo shift moved to %s-%s local", body["start"], body["end"])
    return True


class Simulator:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], seed: int = 11):
        self.sessionmaker = sessionmaker
        self.rng = random.Random(seed)
        self.sims: list[Sim] = []
        self.task: asyncio.Task[None] | None = None
        self.running = False

    async def _load(self, db: AsyncSession) -> tuple[Factory, ShiftWindow]:
        factory = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one()
        shift = await current_shift(db, factory)
        rows = (
            await db.execute(
                select(Station, WorkerAssignment, Operation)
                .outerjoin(WorkerAssignment, (WorkerAssignment.station_id == Station.id) & WorkerAssignment.valid_to.is_(None))
                .outerjoin(Operation, Operation.id == WorkerAssignment.operation_id)
                .order_by(Station.id)
            )
        ).all()
        self.sims = [
            Sim(s, float(op.smv) if op else 0.5, wa.worker_id if wa else None, wa.operation_id if wa else None)
            for s, wa, op in rows
        ]
        # resume after a restart: keep today's counts and each station's last state
        by_id = {sim.station.id: sim for sim in self.sims}
        for pe in (
            await db.execute(
                select(ProductionEntry).where(ProductionEntry.period_start >= shift.start, ProductionEntry.source == "simulator")
            )
        ).scalars():
            if pe.station_id in by_id:
                by_id[pe.station_id].hour_units[pe.period_start] = float(pe.qty_accepted)
        for lv in (await db.execute(select(StationLive))).scalars():
            if lv.station_id in by_id and lv.worker_state:
                by_id[lv.station_id].state = {"uncertain": "off"}.get(lv.worker_state, lv.worker_state)
        return factory, shift

    async def _flush_production(self, db: AsyncSession, only_hour: datetime | None = None) -> None:
        """Write each station's units per hour as one simulator production entry (updated in place)."""
        hours = {h for sim in self.sims for h in sim.hour_units if only_hour is None or h == only_hour}
        for hour in hours:
            existing = {
                r.station_id: r
                for r in (
                    await db.execute(
                        select(ProductionEntry).where(ProductionEntry.period_start == hour, ProductionEntry.source == "simulator")
                    )
                ).scalars()
            }
            for sim in self.sims:
                units = sim.hour_units.get(hour)
                if units is None or sim.operation_id is None:
                    continue
                row, qty = existing.get(sim.station.id), int(units)
                if row is None:
                    db.add(
                        ProductionEntry(
                            worker_id=sim.worker_id,
                            station_id=sim.station.id,
                            operation_id=sim.operation_id,
                            period_start=hour,
                            period_end=hour + timedelta(hours=1),
                            qty_accepted=qty,
                            qty_rework=qty // 30,
                            source="simulator",
                            status="confirmed",
                        )
                    )
                elif row.qty_accepted != qty:
                    row.qty_accepted, row.qty_rework = qty, qty // 30
        await db.commit()

    async def backfill(self) -> None:
        """Replay today's shift up to now, unless it already has events."""
        async with self.sessionmaker() as db:
            factory = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one()
            await ensure_demo_shift(db, factory)
            _, shift = await self._load(db)
            now = utcnow()
            already = (
                await db.execute(select(Event.id).where(Event.start_time >= shift.start, Event.source == "simulator").limit(1))
            ).first()
            if already or now <= shift.start:
                return
            t, batch = shift.start, []
            for sim in self.sims:
                batch += _transition(sim, "working", t, self.rng)
            while t < min(now, shift.end):
                for sim in self.sims:
                    batch += _step(sim, t, 1.0, shift, self.rng)
                t += timedelta(minutes=1)
            await self._bulk_insert(db, batch)
            await self._flush_production(db)
            log.info("simulator backfilled %d events", len(batch))

    async def _bulk_insert(self, db: AsyncSession, batch: list[EventIn]) -> None:
        """Fast path for the replay: rows go straight in; live state is set from each station's last transition."""
        by_code = {sim.station.code: sim for sim in self.sims}
        rows, live = [], {}
        for e in batch:
            sim = by_code[e.station_code]
            rows.append(
                {
                    "event_uuid": e.event_uuid,
                    "event_type": e.event_type,
                    "state": e.state,
                    "station_id": sim.station.id,
                    "worker_id": sim.worker_id,
                    "operation_id": sim.operation_id,
                    "source": "simulator",
                    "start_time": e.start_time,
                    "confidence": e.confidence,
                    "model_version": e.model_version,
                    "review_status": review_status(e.event_type, e.state, e.confidence),
                    "meta": {},
                    "received_at": utcnow(),
                }
            )
            live.setdefault(sim.station.id, {})[e.event_type] = (e.state, e.start_time)
        for i in range(0, len(rows), 5000):
            await db.execute(insert(Event), rows[i : i + 5000])
        for sid, states in live.items():
            lv = await db.get(StationLive, sid) or StationLive(station_id=sid)
            if "worker_state" in states:
                lv.worker_state, lv.worker_since = states["worker_state"]
            if "machine_state" in states:
                lv.machine_state, lv.machine_since = states["machine_state"]
            db.add(lv)
        await db.commit()

    async def tick(self) -> None:
        async with self.sessionmaker() as db:
            factory = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one()
            if await ensure_demo_shift(db, factory):
                await self._load(db)
            shift, now = await current_shift(db, factory), utcnow()
            events: list[EventIn] = []
            for sim in self.sims:
                events += _step(sim, now, TICK_S / 60, shift, self.rng)
            if events:
                await ingest_batch(db, events, "simulator", None)
            await self._heartbeat(db, now)
            await self._flush_production(db, now.replace(minute=0, second=0, microsecond=0))

    async def _heartbeat(self, db: AsyncSession, now: datetime) -> None:
        devices = list((await db.execute(select(Device).where(Device.is_active).order_by(Device.id))).scalars())
        cameras = [d for d in devices if d.kind == "camera"]
        offline = {d.id for d in cameras[-OFFLINE_CAMERAS:]}
        for d in devices:
            if d.id not in offline:
                d.last_seen_at = now
        lives = {lv.station_id: lv for lv in (await db.execute(select(StationLive))).scalars()}
        for d in cameras:
            if d.id in offline and d.station_id in lives and lives[d.station_id].worker_state != "uncertain":
                await ingest_batch(
                    db,
                    [
                        EventIn(
                            event_uuid=uuid.uuid4(),
                            event_type="worker_state",
                            state="uncertain",
                            station_code=next(s.station.code for s in self.sims if s.station.id == d.station_id),
                            start_time=now,
                        )
                    ],
                    "simulator",
                    None,
                )
                for s in self.sims:
                    if s.station.id == d.station_id:
                        s.state = "off"
        await db.commit()

    async def _run(self) -> None:
        try:
            await self.backfill()
        except Exception:
            log.exception("simulator backfill failed")
        while self.running:
            try:
                await self.tick()
            except Exception:
                log.exception("simulator tick failed")
            await asyncio.sleep(TICK_S)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._run(), name="simulator")

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
