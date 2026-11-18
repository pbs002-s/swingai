from sqlalchemy import select

from app.main import app
from app.models import AuditLog, Factory
from app.modules import imports, setup, setup_users

if not any(getattr(r, "path", "") == "/api/v1/factories" for r in app.routes):  # mount once until main.py lists them
    for _r in (setup.router, setup_users.router, imports.router):
        app.include_router(_r, prefix="/api/v1")


async def factory_id(db) -> int:
    return (await db.execute(select(Factory.id).where(Factory.code == "U2"))).scalar_one()


async def test_supervisor_cannot_change_setup(supervisor, db):
    fid = await factory_id(db)
    for path, body in (
        ("/factories", {"code": "X1", "name": "X"}),
        ("/floors", {"factory_id": fid, "code": "FX", "name": "X"}),
        ("/catalog/machine-brands", {"name": "Nope"}),
        ("/workers", {"factory_id": fid, "employee_code": "E-X", "full_name": "X"}),
    ):
        r = await supervisor.post(path, json=body)
        assert r.status_code == 403, (path, r.text)
    assert (await supervisor.get("/users")).status_code == 403
    assert (await supervisor.get("/catalog/machine-types")).status_code == 200  # read is open to staff


async def test_factory_timezone_is_validated_and_settings_merge(admin, db):
    r = await admin.post("/factories", json={"code": "TZ1", "name": "Unit TZ", "timezone": "Mars/Olympus"})
    assert r.status_code == 400
    r = await admin.post("/factories", json={"code": "TZ1", "name": "Unit TZ", "settings": {"face_blur": True}})
    assert r.status_code == 201, r.text
    fid = r.json()["data"]["id"]
    r = await admin.patch(f"/factories/{fid}", json={"timezone": "Europe/Berlin", "settings": {"card_tap_enabled": True}})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["timezone"] == "Europe/Berlin"
    assert r.json()["data"]["settings"] == {"face_blur": True, "card_tap_enabled": True}
    assert (await admin.patch(f"/factories/{fid}", json={"timezone": "../etc/passwd"})).status_code == 400
    assert (await admin.patch(f"/factories/{fid}", json={"settings": {"unknown": 1}})).status_code == 400
    assert (await admin.patch(f"/factories/{fid}", json={"name": None})).status_code == 400
    assert (await admin.post("/factories", json={"code": "TZ1", "name": "Again"})).json()["error"]["code"] == "DUPLICATE"
    logged = (
        await db.execute(select(AuditLog).where(AuditLog.action == "factory.update", AuditLog.entity_id == str(fid)))
    ).first()
    assert logged is not None


async def test_structure_floor_line_station(admin, db):
    fid = await factory_id(db)
    floor = (await admin.post("/floors", json={"factory_id": fid, "code": "FS", "name": "Setup floor"})).json()["data"]
    line = (await admin.post("/lines", json={"floor_id": floor["id"], "code": "LS", "name": "Setup line"})).json()["data"]
    r = await admin.post("/stations", json={"line_id": line["id"], "code": "LS-S001"})
    assert r.status_code == 201 and r.json()["data"]["name"] == "LS-S001" and r.json()["data"]["position"] == 1
    sid = r.json()["data"]["id"]
    r = await admin.post("/stations", json={"line_id": line["id"], "code": "LS-S001"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE"
    assert (await admin.patch(f"/stations/{sid}", json={"status": "broken"})).status_code == 400
    assert (await admin.patch(f"/stations/{sid}", json={"status": "maintenance"})).json()["data"]["status"] == "maintenance"
    listed = (await admin.get(f"/stations?line_id={line['id']}")).json()["data"]
    assert [s["code"] for s in listed] == ["LS-S001"]
    assert (await admin.patch(f"/lines/{line['id']}", json={"is_active": False})).json()["data"]["is_active"] is False
    assert (await admin.post("/lines", json={"floor_id": 999999, "code": "Q", "name": "Q"})).status_code == 404
    assert (await admin.patch("/stations/999999", json={"name": "x"})).status_code == 404


async def test_lists_and_machine_validation_and_placement(admin, db):
    fid = await factory_id(db)
    t = await admin.post("/catalog/machine-types", json={"code": "BTK", "name": "Bartack", "name_bn": "বারট্যাক"})
    assert t.status_code == 201, t.text
    assert (await admin.post("/catalog/machine-types", json={"code": "BTK", "name": "Dup"})).status_code == 409
    b = await admin.post("/catalog/machine-brands", json={"name": "Pegasus"})
    assert b.status_code == 201
    bad = await admin.post(
        "/machines", json={"factory_id": fid, "asset_code": "M-SET1", "machine_type": "BTK", "brand": "Nobrand"}
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNKNOWN_LIST_VALUE"
    m = await admin.post(
        "/machines", json={"factory_id": fid, "asset_code": "M-SET1", "machine_type": "bartack", "brand": "pegasus"}
    )
    assert m.status_code == 201, m.text
    assert m.json()["data"]["machine_type"] == "BTK" and m.json()["data"]["brand"] == "Pegasus"
    mid = m.json()["data"]["id"]

    # renaming a brand follows through to its machines; a deactivated type is refused
    await admin.patch(f"/catalog/machine-brands/{b.json()['data']['id']}", json={"name": "Pegasus Co"})
    assert (await admin.get(f"/machines/{mid}")).json()["data"]["brand"] == "Pegasus Co"
    await admin.patch(f"/catalog/machine-types/{t.json()['data']['id']}", json={"is_active": False})
    assert (await admin.patch(f"/machines/{mid}", json={"machine_type": "BTK"})).status_code == 422

    line = (await admin.get("/lines")).json()["data"][0]
    st = [(await admin.post("/stations", json={"line_id": line["id"], "code": f"MP-S{n}"})).json()["data"] for n in (1, 2)]
    r = await admin.post(f"/machines/{mid}/assign", json={"station_id": st[0]["id"], "valid_from": "2030-01-01T08:00:00Z"})
    assert r.status_code == 201, r.text
    r = await admin.post(f"/machines/{mid}/assign", json={"station_id": st[1]["id"], "valid_from": "2029-12-31T08:00:00Z"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ASSIGNMENT_OVERLAP"
    r = await admin.post(f"/machines/{mid}/assign", json={"station_id": st[1]["id"], "valid_from": "2030-01-02T08:00:00Z"})
    assert r.status_code == 201
    assert (
        await admin.post(f"/machines/{mid}/assign", json={"station_id": st[1]["id"], "valid_from": "2030-01-01T09:00"})
    ).status_code == 400
    found = (await admin.get("/machines?q=M-SET1")).json()["data"]
    assert found[0]["station"]["id"] == st[1]["id"]


async def test_operations_and_reason_codes(admin):
    p = (await admin.post("/products", json={"code": "P-SET", "name": "Setup tee"})).json()["data"]
    assert (
        await admin.post("/operations", json={"product_id": p["id"], "code": "OP-SET", "name": "Hem", "smv": 0})
    ).status_code == 400
    r = await admin.post("/operations", json={"product_id": p["id"], "code": "OP-SET", "name": "Hem", "smv": "0.415"})
    assert r.status_code == 201 and r.json()["data"]["smv"] == 0.415
    r = await admin.post("/catalog/reason-codes", json={"category": "downtime", "code": "OIL", "name": "Oiling"})
    assert r.status_code == 201
    codes = (await admin.get("/catalog/reason-codes?category=downtime")).json()["data"]
    assert "OIL" in {c["code"] for c in codes} and {c["category"] for c in codes} == {"downtime"}


async def test_workers_and_assignment_end(admin, db):
    fid = await factory_id(db)
    w = await admin.post(
        "/workers", json={"factory_id": fid, "employee_code": "E-SET1", "full_name": "Setup Worker", "rfid_card_id": "CARD-SET1"}
    )
    assert w.status_code == 201, w.text
    dup = await admin.post(
        "/workers", json={"factory_id": fid, "employee_code": "E-SET2", "full_name": "X", "rfid_card_id": "CARD-SET1"}
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DUPLICATE"
    wid = w.json()["data"]["id"]
    assert (await admin.patch(f"/workers/{wid}", json={"rfid_card_id": ""})).json()["data"]["rfid_card_id"] is None

    st = (
        await admin.post("/stations", json={"line_id": (await admin.get("/lines")).json()["data"][0]["id"], "code": "WS-S001"})
    ).json()["data"]
    op = (await admin.get("/operations")).json()["data"][0]
    a = await admin.post("/assignments", json={"worker_id": wid, "station_id": st["id"], "operation_id": op["id"]})
    assert a.status_code == 201, a.text
    active = (await admin.get(f"/assignments?station_id={st['id']}&active=true")).json()["data"]
    assert [x["worker"]["employee_code"] for x in active] == ["E-SET1"]
    assert (await admin.post(f"/assignments/{a.json()['data']['id']}/end")).status_code == 200
    assert (await admin.post(f"/assignments/{a.json()['data']['id']}/end")).status_code == 409
    assert (await admin.get(f"/assignments?station_id={st['id']}&active=true")).json()["data"] == []


async def test_user_admin_never_leaks_the_hash(admin, anon):
    body = {
        "email": "New.Sup@Example.com",
        "full_name": "New supervisor",
        "password": "a-long-password-1",
        "roles": [{"role": "supervisor", "scope_type": "all"}],
    }
    assert (await admin.post("/users", json={**body, "password": "short"})).status_code == 400
    assert (await admin.post("/users", json={**body, "roles": [{"role": "king"}]})).status_code == 400
    assert (await admin.post("/users", json={**body, "roles": [{"role": "supervisor", "scope_type": "line"}]})).status_code == 400
    r = await admin.post("/users", json=body)
    assert r.status_code == 201, r.text
    assert "password" not in r.text and r.json()["data"]["email"] == "new.sup@example.com"
    uid = r.json()["data"]["id"]
    assert (await admin.post("/users", json=body)).status_code == 409
    listed = await admin.get("/users")
    assert "password_hash" not in listed.text and "$argon2" not in listed.text

    r = await admin.put(f"/users/{uid}/roles", json=[{"role": "quality", "scope_type": "line", "scope_id": 999999}])
    assert r.status_code == 404
    r = await admin.put(f"/users/{uid}/roles", json=[{"role": "quality", "scope_type": "all"}])
    assert [x["role"] for x in r.json()["data"]["roles"]] == ["quality"]
    assert (await admin.post(f"/users/{uid}/reset-password", json={"password": "another-long-pass"})).status_code == 200
    login = await anon.post("/auth/login", json={"email": "new.sup@example.com", "password": "another-long-pass"})
    assert login.status_code == 200
    assert (await admin.patch(f"/users/{uid}", json={"is_active": False})).json()["data"]["is_active"] is False

    me = (await admin.get("/auth/me")).json()["data"]["id"]
    assert (await admin.patch(f"/users/{me}", json={"is_active": False})).status_code == 422
    assert (await admin.put(f"/users/{me}/roles", json=[{"role": "factory_admin"}])).status_code == 422
