"""Cameras, the edge job queue and the simulated edge box."""

import base64

import pytest
from sqlalchemy import select

from app.core.db import utcnow
from app.core.security import new_token, sha256
from app.main import app
from app.models import Device, Station
from app.models.edge import EdgeJob
from app.modules import cameras
from app.modules.edge_sim import run_simulated_edge_jobs

if not getattr(app.state, "cameras_mounted", False):  # router is not in main.py yet
    app.include_router(cameras.router, prefix="/api/v1")
    app.state.cameras_mounted = True

CONN = {"host": "10.20.0.21", "port": 554, "rtsp_path": "/Streaming/Channels/101", "username": "admin", "password": "s3cret-cam"}


async def _edge_id(db, code: str = "EDGE-1") -> int:
    return (await db.execute(select(Device.id).where(Device.code == code))).scalar_one()


async def _stations(db, n: int = 2) -> list[int]:
    return list((await db.execute(select(Station.id).order_by(Station.id).limit(n))).scalars())


@pytest.fixture
async def sim_box(db) -> int:
    box = (await db.execute(select(Device).where(Device.code == "EDGE-SIM"))).scalar_one_or_none()
    if box is None:
        box = Device(code="EDGE-SIM", kind="edge_box", config={"name": "Sim", "simulated": True}, last_seen_at=utcnow())
        db.add(box)
        await db.commit()
    return box.id


async def _create_camera(admin, db, edge_id: int, **over) -> dict:
    body = {"edge_box_id": edge_id, "name": "Line 1 cam A", "connection": CONN, "station_ids": await _stations(db), **over}
    r = await admin.post("/cameras", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def test_job_round_trip_with_real_edge(admin, device, db):
    from app.models import Device

    edge = await _edge_id(db)
    box = await db.get(Device, edge)
    box.config = {k: v for k, v in (box.config or {}).items() if k != "simulated"}  # behave like a real edge box
    await db.commit()
    r = await admin.post(f"/edge-boxes/{edge}/jobs", json={"kind": "test_camera", "params": {"connection": CONN}})
    assert r.status_code == 201, r.text
    job = r.json()["data"]
    assert job["status"] == "queued" and "password" not in job["params"]["connection"]

    polled = (await device.get("/edge/jobs")).json()["data"]
    mine = next(j for j in polled if j["id"] == job["id"])
    assert mine["params"]["connection"]["password"] == "s3cret-cam"  # only the edge box sees it
    assert (await device.get("/edge/jobs")).json()["data"] == []  # now running, not handed out twice

    res = {"status": "done", "result": {"resolution": "1920x1080", "fps": 25, "codec": "H.264", "latency_ms": 90}}
    assert (await device.post(f"/edge/jobs/{job['id']}/result", json=res)).status_code == 200
    assert (await device.post(f"/edge/jobs/{job['id']}/result", json=res)).status_code == 409
    seen = (await admin.get(f"/edge-boxes/{edge}/jobs/{job['id']}")).json()["data"]
    assert seen["status"] == "done" and seen["result"]["codec"] == "H.264"


async def test_job_params_validated(admin, db):
    edge = await _edge_id(db)
    assert (await admin.post(f"/edge-boxes/{edge}/jobs", json={"kind": "test_camera", "params": {}})).status_code == 400
    assert (await admin.post(f"/edge-boxes/{edge}/jobs", json={"kind": "reboot"})).status_code == 400
    bad = [{**CONN, "host": "bad host"}, {**CONN, "port": 0}, {**CONN, "rtsp_path": "stream"}, {**CONN, "password": "a\nb"}]
    for conn in bad:
        r = await admin.post(f"/edge-boxes/{edge}/jobs", json={"kind": "test_camera", "params": {"connection": conn}})
        assert r.status_code == 400, conn


async def test_simulated_edge_completes_jobs(admin, db, sim_box):
    scan = (await admin.post(f"/edge-boxes/{sim_box}/jobs", json={"kind": "discover_cameras"})).json()["data"]
    wrong = {**CONN, "password": "wrong"}
    bad = (await admin.post(f"/edge-boxes/{sim_box}/jobs", json={"kind": "test_camera", "params": {"connection": wrong}})).json()
    good = (await admin.post(f"/edge-boxes/{sim_box}/jobs", json={"kind": "test_camera", "params": {"connection": CONN}})).json()
    await run_simulated_edge_jobs(db)  # the background run may already have done them; either way they finish

    scan = (await admin.get(f"/edge-boxes/{sim_box}/jobs/{scan['id']}")).json()["data"]
    assert scan["status"] == "done" and 3 <= len(scan["result"]["cameras"]) <= 4
    assert all(c["host"].startswith("10.20.0.") for c in scan["result"]["cameras"])
    bad = (await admin.get(f"/edge-boxes/{sim_box}/jobs/{bad['data']['id']}")).json()["data"]
    assert bad["status"] == "failed" and bad["error"] == "Authentication failed (401)"
    good = (await admin.get(f"/edge-boxes/{sim_box}/jobs/{good['data']['id']}")).json()["data"]
    assert good["status"] == "done" and good["result"]["resolution"] == "1920x1080"
    snap = good["result"]["snapshot"]
    assert snap.startswith("data:image/svg+xml;base64,") and len(snap) < 40_000
    assert base64.b64decode(snap.split(",", 1)[1]).startswith(b"<svg")

    cam = await _create_camera(admin, db, sim_box)
    det = await admin.post(f"/edge-boxes/{sim_box}/jobs", json={"kind": "test_detection", "params": {"camera_id": cam["id"]}})
    await run_simulated_edge_jobs(db)
    det = (await admin.get(f"/edge-boxes/{sim_box}/jobs/{det.json()['data']['id']}")).json()["data"]
    assert det["status"] == "done" and {d["label"] for d in det["result"]["detections"]} == {"person", "phone"}
    listed = next(c for c in (await admin.get("/cameras")).json()["data"] if c["id"] == cam["id"])
    assert listed["online"] is True


async def test_password_encrypted_and_only_sent_to_edge(admin, device, db):
    edge = await _edge_id(db)
    cam = await _create_camera(admin, db, edge)
    assert "password" not in cam["connection"] and cam["connection"]["has_password"] is True

    row = await db.get(Device, cam["id"])
    stored = row.config["connection"]
    assert "password" not in stored and "s3cret-cam" not in str(row.config)
    assert cameras.decrypt(stored["password_enc"]) == "s3cret-cam"
    assert "s3cret-cam" not in (await admin.get("/cameras")).text

    cfg = (await device.get("/edge/config")).json()["data"]
    mine = next(c for c in cfg["cameras"] if c["id"] == cam["id"])
    assert mine["connection"]["password"] == "s3cret-cam"
    assert (await admin.get("/edge/config")).status_code == 401  # a user session is not a device token

    jobs = list((await db.execute(select(EdgeJob).where(EdgeJob.edge_device_id == edge))).scalars())
    assert all("s3cret-cam" not in str(j.params) for j in jobs)


async def test_zone_validation_and_patch(admin, db):
    edge = await _edge_id(db)
    cam = await _create_camera(admin, db, edge)
    st = cam["stations"][0]["id"]
    tri = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.6]]
    ok_body = {"zones": [{"station_id": st, "kind": "work", "points": tri}, {"kind": "privacy", "points": tri}]}
    r = await admin.put(f"/cameras/{cam['id']}/zones", json=ok_body)
    assert r.status_code == 200 and r.json()["data"]["zones_count"] == 2

    bad = [
        {"zones": [{"station_id": st, "kind": "work", "points": tri[:2]}]},  # too few points
        {"zones": [{"station_id": st, "kind": "work", "points": [[1.2, 0], [0, 0], [0, 1]]}]},  # outside 0-1
        {"zones": [{"kind": "work", "points": tri}]},  # work zone without a station
        {"zones": [{"station_id": st, "kind": "door", "points": tri}]},
        {"zones": [{"station_id": st, "kind": "work", "points": [[0.1, 0.1]] * 33}]},
    ]
    for body in bad:
        assert (await admin.put(f"/cameras/{cam['id']}/zones", json=body)).status_code == 400, body
    other = (await _stations(db, 5))[4]
    r = await admin.put(f"/cameras/{cam['id']}/zones", json={"zones": [{"station_id": other, "kind": "work", "points": tri}]})
    assert r.json()["error"]["code"] == "ZONE_STATION_NOT_ASSIGNED"

    r = await admin.patch(
        f"/cameras/{cam['id']}", json={"fps": 10, "purpose": "seam_inspection", "station_ids": [cam["stations"][1]["id"]]}
    )
    data = r.json()["data"]
    assert data["fps"] == 10 and data["purpose"] == "seam_inspection" and data["zones_count"] == 1  # stale work zone dropped
    assert (await admin.patch(f"/cameras/{cam['id']}", json={"fps": 30})).status_code == 400
    assert (await admin.delete(f"/cameras/{cam['id']}")).json()["data"]["is_active"] is False


async def test_camera_create_validation(admin, db):
    edge = await _edge_id(db)
    st = await _stations(db, 3)
    base = {"edge_box_id": edge, "name": "x", "connection": CONN}
    for body in ({**base, "station_ids": st}, {**base, "station_ids": []}, {**base, "station_ids": [st[0], st[0]]}):
        assert (await admin.post("/cameras", json=body)).status_code == 400, body
    assert (await admin.post("/cameras", json={**base, "station_ids": [999999]})).json()["error"]["code"] == "UNKNOWN_STATION"


async def test_rbac(supervisor, anon, db):
    edge = await _edge_id(db)
    assert (await supervisor.get("/cameras")).status_code == 403
    assert (await supervisor.post(f"/edge-boxes/{edge}/jobs", json={"kind": "discover_cameras"})).status_code == 403
    body = {"edge_box_id": edge, "name": "x", "connection": CONN, "station_ids": await _stations(db, 1)}
    assert (await supervisor.post("/cameras", json=body)).status_code == 403
    assert (await supervisor.put("/cameras/1/zones", json={"zones": []})).status_code == 403

    sensor = (await db.execute(select(Device).where(Device.kind == "machine_sensor").limit(1))).scalar_one()
    token = new_token()
    sensor.token_hash = sha256(token)
    await db.commit()
    r = await anon.get("/edge/jobs", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_NOT_EDGE"


async def test_live_wall_urls_and_access(admin, supervisor, anon, db):
    edge = await _edge_id(db)
    box = await db.get(Device, edge)
    box.config = {**(box.config or {}), "live_base": "http://10.20.0.5:1984/"}
    await db.commit()
    cam = await _create_camera(admin, db, edge)

    r = await supervisor.get("/cameras/live")  # supervisors can watch, not edit
    assert r.status_code == 200, r.text
    row = next(c for c in r.json()["data"] if c["id"] == cam["id"])
    assert row["live"] == {"mode": "embed", "url": f"http://10.20.0.5:1984/stream.html?src={cam['code']}&mode=webrtc,mse"}
    assert row["privacy_zones"] == 0  # the wall warns about a camera with nothing masked
    assert "s3cret-cam" not in r.text and "connection" not in row  # the camera password never reaches the browser
    assert (await anon.get("/cameras/live")).status_code == 401


async def test_browser_test_camera_frames(admin, supervisor, anon, monkeypatch):
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg").decode()
    cam = (await admin.post("/cameras/test-source", json={"name": "Lab laptop"})).json()["data"]

    assert (await supervisor.get(f"/cameras/{cam['id']}/frame.jpg")).status_code == 404  # nothing sent yet
    assert (await admin.put(f"/cameras/{cam['id']}/frame", json={"jpeg": base64.b64encode(b"nope").decode()})).status_code == 400
    assert (await admin.put(f"/cameras/{cam['id']}/frame", json={"jpeg": jpeg})).status_code == 200
    assert (await supervisor.put(f"/cameras/{cam['id']}/frame", json={"jpeg": jpeg})).status_code == 403  # only admins publish

    r = await supervisor.get(f"/cameras/{cam['id']}/frame.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")
    assert (await anon.get(f"/cameras/{cam['id']}/frame.jpg")).status_code == 401
    row = next(c for c in (await supervisor.get("/cameras/live")).json()["data"] if c["id"] == cam["id"])
    assert row["online"] and row["live"]["mode"] == "frames"

    monkeypatch.setattr(cameras, "FRAME_FRESH_S", -1.0)  # frames go stale when the browser stops sending
    assert (await supervisor.get(f"/cameras/{cam['id']}/frame.jpg")).status_code == 404

    monkeypatch.setattr(cameras.get_settings(), "env", "production")
    assert (await admin.post("/cameras/test-source", json={"name": "x"})).json()["error"]["code"] == "TEST_CAMERA_DISABLED"
