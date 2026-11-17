from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.db import utcnow
from app.models import Alert, Station, StationLive
from app.modules.alerts import evaluate_rules
from app.modules.floor import tile_state
from app.modules.shift import window_for


def test_night_shift_belongs_to_the_day_it_started():
    body = {"start": "22:00", "end": "06:00", "crosses_midnight": True, "breaks": [{"start": "02:00", "end": "02:30"}]}
    now = datetime(2026, 11, 18, 1, 0, tzinfo=ZoneInfo("Asia/Dhaka")).astimezone(UTC)
    w = window_for(body, "Asia/Dhaka", now)
    assert w.start.astimezone(w.tz).day == 17 and w.end.astimezone(w.tz).day == 18
    assert w.worked_minutes(now) == 180
    assert w.worked_minutes(w.end) == 8 * 60 - 30


def test_tile_state_rules():
    now = utcnow()
    live = StationLive(worker_state="idle", machine_state="stopped", machine_since=now - timedelta(minutes=20))
    assert tile_state(live, now, 5) == "down"
    assert tile_state(StationLive(worker_state="working", machine_state="running"), now, 5) == "running"
    assert tile_state(None, now, 5) == "no_data"
    assert tile_state(StationLive(worker_state="uncertain"), now, 5) == "no_data"


async def test_overview_floor_and_timeline_respond(admin, db):
    ov = (await admin.get("/overview")).json()["data"]
    assert ov["totals"]["stations"] == 144 and len(ov["lines"]) == 6 and ov["hourly"]
    line_id = ov["lines"][2]["id"]
    fl = (await admin.get(f"/floor?line_id={line_id}")).json()["data"]
    assert len(fl["stations"]) == 24 and fl["stations"][0]["worker"]
    tl = await admin.get(f"/stations/{fl['stations'][0]['id']}/timeline")
    assert tl.status_code == 200 and set(tl.json()["data"]["lanes"]) == {"worker_state", "machine_state"}


async def test_unknown_line_is_404(admin):
    assert (await admin.get("/floor?line_id=99999")).status_code == 404


async def test_long_machine_stop_raises_one_alert_and_resolves(db):
    from app.models import Factory
    from app.simulator.engine import ensure_demo_shift

    await ensure_demo_shift(db, (await db.execute(select(Factory))).scalars().first())  # alerts only run inside a shift
    st = (await db.execute(select(Station).where(Station.code == "L5-S20"))).scalar_one()
    since = utcnow() - timedelta(minutes=40)
    live = await db.get(StationLive, st.id) or StationLive(station_id=st.id)
    live.worker_state, live.worker_since, live.machine_state, live.machine_since = "idle", since, "stopped", since
    db.add(live)
    await db.commit()
    await evaluate_rules(db)
    await evaluate_rules(db)
    alerts = list((await db.execute(select(Alert).where(Alert.station_id == st.id, Alert.status == "open"))).scalars())
    assert len([a for a in alerts if a.title.startswith("Machine stopped")]) == 1
    live.machine_state, live.machine_since, live.worker_state = "running", utcnow(), "working"
    await db.commit()
    await evaluate_rules(db)
    await db.refresh(alerts[0])
    assert all(a.status == "resolved" for a in (await db.execute(select(Alert).where(Alert.station_id == st.id))).scalars())


async def test_alert_center_ack_and_rule_edit(admin, supervisor):
    items = (await admin.get("/alerts")).json()
    if items["data"]:
        aid = items["data"][0]["id"]
        assert (await supervisor.post(f"/alerts/{aid}/ack")).json()["data"]["status"] == "acknowledged"
    rules = (await admin.get("/alert-rules")).json()["data"]
    rid = rules[0]["id"]
    assert (await supervisor.patch(f"/alert-rules/{rid}", json={"is_enabled": False})).status_code == 403
    bad = await admin.patch(f"/alert-rules/{rid}", json={"condition": {"bogus": 1}})
    assert bad.status_code == 400
    r = await admin.patch(f"/alert-rules/{rid}", json={"condition": {"min_minutes": 20}, "severity": "warning"})
    assert r.json()["data"]["condition"]["min_minutes"] == 20


async def test_bulk_stations_and_rbac(admin, supervisor):
    tree = (await admin.get("/org/tree")).json()["data"]
    line_id = tree[0]["floors"][0]["lines"][0]["id"]
    body = {"line_id": line_id, "prefix": "T-", "start": 1, "count": 100}
    assert (await supervisor.post("/stations/bulk", json=body)).status_code == 403
    r = await admin.post("/stations/bulk", json=body)
    assert r.status_code == 201 and r.json()["data"]["created"] == 100
    assert (await admin.post("/stations/bulk", json=body)).status_code == 409


async def test_needle_lot_b104_shows_a_batch_pattern(admin):
    stats = (await admin.get("/needles/stats")).json()["data"]
    b104 = next(s for s in stats if s["lot_no"] == "B-104")
    assert b104["pattern"] == "batch" and b104["confirmed_breaks"] == 8
    c077 = next(s for s in stats if s["lot_no"] == "C-077")
    assert c077["pattern"] == "too_little_use"
    q = await admin.post(f"/needle-batches/{b104['batch_id']}/quarantine")
    assert q.json()["data"]["status"] == "quarantined"
    assert (await admin.post(f"/needle-batches/{b104['batch_id']}/quarantine")).status_code == 409


async def test_health_and_security_headers(anon):
    r = await anon.get("/healthz")
    assert r.status_code == 200 and r.headers["x-frame-options"] == "DENY"
    assert (await anon.get("/readyz")).json()["data"]["database"] == "ok"
