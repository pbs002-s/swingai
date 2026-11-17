import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.db import utcnow
from app.core.security import hash_password
from app.models import Event, Line, Station, User, UserRole
from app.simulator.seed import DEMO_PASSWORD
from tests.conftest import login_as


async def test_locked_account_gets_the_same_answer_as_a_wrong_password(anon, db):
    u = User(email="locked@stitchsense.local", full_name="Locked", password_hash=hash_password(DEMO_PASSWORD))
    u.roles = [UserRole(role="supervisor")]
    u.locked_until = utcnow() + timedelta(minutes=10)
    db.add(u)
    await db.commit()
    r = await anon.post("/auth/login", json={"email": "locked@stitchsense.local", "password": DEMO_PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_line_scoped_supervisor_cannot_act_on_another_line(device, db):
    lines = list((await db.execute(select(Line).order_by(Line.id))).scalars())
    u = User(email="line1@stitchsense.local", full_name="Line 1 supervisor", password_hash=hash_password(DEMO_PASSWORD))
    u.roles = [UserRole(role="supervisor", scope_type="line", scope_id=lines[0].id)]
    db.add(u)
    await db.commit()
    other = (await db.execute(select(Station).where(Station.line_id == lines[1].id).limit(1))).scalar_one()
    mine = (await db.execute(select(Station).where(Station.line_id == lines[0].id).limit(1))).scalar_one()
    ids = []
    for st in (other, mine):
        ev = {"event_uuid": str(uuid.uuid4()), "event_type": "worker_state", "state": "phone_use",
              "station_code": st.code, "start_time": utcnow().isoformat(), "confidence": 0.9}
        ids.append((await device.post("/ingest/events", json={"events": [ev]})).json()["data"]["results"][0]["event_id"])
    c = await login_as("line1@stitchsense.local")
    assert (await c.post(f"/events/{ids[0]}/review", json={"decision": "confirm"})).status_code == 403
    assert (await c.post(f"/events/{ids[1]}/review", json={"decision": "confirm"})).status_code == 200
    await c.aclose()


async def test_management_cannot_silence_alerts(manager, admin):
    alerts = (await admin.get("/alerts")).json()["data"]
    if alerts:
        assert (await manager.post(f"/alerts/{alerts[0]['id']}/resolve")).status_code == 403


async def test_device_clock_far_ahead_is_refused_and_does_not_freeze_live_state(device, db):
    ahead = {"event_uuid": str(uuid.uuid4()), "event_type": "worker_state", "state": "idle", "station_code": "L6-S01",
             "start_time": (utcnow() + timedelta(hours=3)).isoformat()}
    res = (await device.post("/ingest/events", json={"events": [ahead]})).json()["data"]["results"][0]
    assert res["error"] == "TIME_IN_FUTURE"


async def test_repeated_state_keeps_its_start_time(device, db):
    st = (await db.execute(select(Station).where(Station.code == "L6-S02"))).scalar_one()
    t0 = utcnow() - timedelta(minutes=10)
    for t in (t0, t0 + timedelta(minutes=5)):
        ev = {"event_uuid": str(uuid.uuid4()), "event_type": "worker_state", "state": "away", "station_code": st.code,
              "start_time": t.isoformat(), "confidence": 0.95}
        await device.post("/ingest/events", json={"events": [ev]})
    from app.models import StationLive

    q = select(StationLive).where(StationLive.station_id == st.id).execution_options(populate_existing=True)
    live = (await db.execute(q)).scalar_one()
    assert live.worker_state == "away" and abs((live.worker_since - t0).total_seconds()) < 1


async def test_oversized_metadata_is_refused(device):
    ev = {"event_uuid": str(uuid.uuid4()), "event_type": "worker_state", "state": "working", "station_code": "L6-S03",
          "start_time": utcnow().isoformat(), "metadata": {"blob": "x" * 5000}}
    res = (await device.post("/ingest/events", json={"events": [ev]})).json()["data"]["results"][0]
    assert res["error"] == "METADATA_TOO_LARGE"


async def test_production_entry_refuses_unknown_station(admin):
    now = utcnow()
    body = {"station_id": 999999, "operation_id": 1, "period_start": (now - timedelta(hours=1)).isoformat(),
            "period_end": now.isoformat(), "qty_accepted": 10}
    assert (await admin.post("/production-entries", json=body)).status_code == 404


__all__ = ["Event"]
