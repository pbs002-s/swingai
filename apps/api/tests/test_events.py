import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import utcnow
from app.models import StationLive, WorkerAssignment


def ev(state: str, station: str = "L3-S07", kind: str = "worker_state", at: datetime | None = None, conf: float | None = 0.9):
    return {
        "event_uuid": str(uuid.uuid4()),
        "event_type": kind,
        "state": state,
        "station_code": station,
        "start_time": (at or utcnow()).isoformat(),
        "confidence": conf,
    }


async def test_ingest_needs_a_device_token(anon):
    r = await anon.post("/ingest/events", json={"events": [ev("working")]})
    assert r.status_code == 401 and r.json()["error"]["code"] == "DEVICE_UNKNOWN"


async def test_ingest_accepts_then_marks_duplicates(device):
    e = ev("working")
    first = (await device.post("/ingest/events", json={"events": [e]})).json()["data"]
    again = (await device.post("/ingest/events", json={"events": [e]})).json()["data"]
    assert first["accepted"] == 1 and again["duplicate"] == 1


async def test_bad_rows_are_rejected_one_by_one(device):
    rows = [ev("working"), ev("working", station="NOPE"), ev("dancing")]
    data = (await device.post("/ingest/events", json={"events": rows})).json()["data"]
    errors = sorted(r["error"] or "" for r in data["results"])
    assert data["accepted"] == 1 and errors == ["", "INVALID_EVENT_TYPE", "UNKNOWN_STATION"]


async def test_naive_timestamps_are_refused(device):
    e = ev("working")
    e["start_time"] = "2026-11-17T09:00:00"
    assert (await device.post("/ingest/events", json={"events": [e]})).status_code == 400


async def test_live_state_ignores_older_transitions(device, db):
    now = utcnow()
    await device.post("/ingest/events", json={"events": [ev("idle", "L3-S09", at=now)]})
    await device.post("/ingest/events", json={"events": [ev("working", "L3-S09", at=now - timedelta(minutes=5))]})
    live = (await db.execute(select(StationLive).where(StationLive.station_id.is_not(None)))).scalars()
    states = {lv.station_id: lv.worker_state for lv in live}
    assert "idle" in states.values()


async def test_phone_use_always_waits_for_review_even_at_high_confidence(device, supervisor):
    await device.post("/ingest/events", json={"events": [ev("phone_use", "L3-S11", conf=0.99)]})
    queue = (await supervisor.get("/events/review-queue")).json()
    assert any(i["state"] == "phone_use" and i["station"]["code"] == "L3-S11" for i in queue["data"])


async def test_review_is_recorded_once_and_respects_roles(device, supervisor, manager):
    data = (await device.post("/ingest/events", json={"events": [ev("phone_use", "L3-S12")]})).json()["data"]
    event_id = data["results"][0]["event_id"]
    assert (await manager.post(f"/events/{event_id}/review", json={"decision": "confirm"})).status_code == 403
    ok = await supervisor.post(f"/events/{event_id}/review", json={"decision": "reclassify", "new_state": "working"})
    assert ok.status_code == 200 and ok.json()["data"]["review_status"] == "reclassified"
    again = await supervisor.post(f"/events/{event_id}/review", json={"decision": "confirm"})
    assert again.status_code == 409


async def test_reclassify_needs_a_valid_state(device, supervisor):
    data = (await device.post("/ingest/events", json={"events": [ev("phone_use", "L3-S13")]})).json()["data"]
    eid = data["results"][0]["event_id"]
    assert (await supervisor.post(f"/events/{eid}/review", json={"decision": "reclassify"})).status_code == 400
    bad = await supervisor.post(f"/events/{eid}/review", json={"decision": "reclassify", "new_state": "flying"})
    assert bad.status_code == 400


async def test_events_follow_the_worker_assigned_at_that_time(device, supervisor, db):
    station = "L4-S03"
    wa = (await db.execute(select(WorkerAssignment).where(WorkerAssignment.valid_to.is_(None)).limit(2))).scalars().all()
    from app.models import Station

    st = (await db.execute(select(Station).where(Station.code == station))).scalar_one()
    switch = datetime.now(UTC) - timedelta(minutes=30)
    r = await supervisor.post(
        "/assignments",
        json={
            "worker_id": wa[1].worker_id,
            "station_id": st.id,
            "operation_id": wa[1].operation_id,
            "valid_from": switch.isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    before = ev("idle", station, at=switch - timedelta(minutes=10))
    after = ev("idle", station, at=switch + timedelta(minutes=10))
    res = (await device.post("/ingest/events", json={"events": [before, after]})).json()["data"]["results"]
    from app.models import Event

    rows = {e.id: e for e in (await db.execute(select(Event).where(Event.id.in_([x["event_id"] for x in res])))).scalars()}
    workers = [rows[x["event_id"]].worker_id for x in res]
    assert workers[0] != workers[1] and workers[1] == wa[1].worker_id
