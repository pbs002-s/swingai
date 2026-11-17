import random

from sqlalchemy import func, select

from app.core.db import SessionLocal, utcnow
from app.models import Event, ProductionEntry, StationLive
from app.modules.shift import DEFAULT_SHIFT, window_for
from app.simulator.engine import Simulator, _step


def test_station_goes_on_break_during_the_break_window():
    from app.models import Station
    from app.simulator.engine import Sim

    shift = window_for(DEFAULT_SHIFT, "Asia/Dhaka", utcnow())
    sim = Sim(Station(id=1, code="X", line_id=1, name="X"), 0.5, 1, 1)
    out = _step(sim, shift.breaks[0][0], 1.0, shift, random.Random(1))
    assert sim.state == "break" and {e.state for e in out} == {"break", "stopped"}


async def test_simulator_backfills_and_ticks():
    sim = Simulator(SessionLocal, seed=3)
    await sim.backfill()
    await sim.tick()
    async with SessionLocal() as db:
        assert (await db.execute(select(func.count()).select_from(Event).where(Event.source == "simulator"))).scalar_one() > 100
        assert (await db.execute(select(func.count()).select_from(ProductionEntry))).scalar_one() > 0
        assert (await db.execute(select(func.count()).select_from(StationLive))).scalar_one() >= 140
