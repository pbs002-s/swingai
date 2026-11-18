from sqlalchemy import func, select

from app.main import app
from app.models import Event, Station, Worker, WorkerAssignment
from app.modules import imports, setup, setup_users

if not any(getattr(r, "path", "") == "/api/v1/factories" for r in app.routes):  # mount once until main.py lists them
    for _r in (setup.router, setup_users.router, imports.router):
        app.include_router(_r, prefix="/api/v1")


def upload(text: str, bom: bool = False) -> dict:
    raw = ("﻿" if bom else "") + text
    return {"file": ("data.csv", raw.encode("utf-8"), "text/csv")}


async def test_import_needs_factory_admin(supervisor):
    r = await supervisor.post("/import/org", files=upload("factory_code\nU2\n"))
    assert r.status_code == 403


async def test_bad_header_is_rejected(admin):
    r = await admin.post("/import/org", files=upload("factory_code,floor\nU2,X\n"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_HEADER"
    assert "line_code" in r.json()["error"]["details"]["missing"]
    assert (await admin.post("/import/unknown", files=upload("a\n1\n"))).status_code == 400
    r = await admin.post("/import/org", files={"file": ("x.csv", b"\xff\xfe\x00", "text/csv")})
    assert r.json()["error"]["code"] == "BAD_ENCODING"


async def test_org_preview_reports_row_errors_and_writes_nothing(admin, db):
    csv = (
        "factory_code,floor_code,floor_name,line_code,line_name,station_code,station_name\n"
        "U2,FI,Import floor,LI,Import line,LI-S001,Station 1\n"
        "NOPE,FI,Import floor,LI,Import line,LI-S002,\n"
        "U2,FI,Import floor,LI,,LI-S003,\n"
        "U2,FI,Import floor,LI,Import line,bad code!,\n"
    )
    r = await admin.post("/import/org", files=upload(csv, bom=True))
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert (d["create"], d["update"], d["committed"]) == (1, 0, False)
    assert [(e["row"], e["column"]) for e in d["errors"]] == [(3, "factory_code"), (4, "line_name"), (5, "station_code")]
    assert (await db.execute(select(Station).where(Station.code == "LI-S001"))).first() is None

    r = await admin.post("/import/org?commit=true", files=upload(csv))
    assert r.json()["data"]["committed"] is True
    assert (await db.execute(select(Station).where(Station.code == "LI-S001"))).scalar_one().name == "Station 1"
    again = (await admin.post("/import/org", files=upload(csv))).json()["data"]
    assert (again["create"], again["update"]) == (0, 1)


async def test_machines_and_workers_import(admin, db):
    await admin.post("/catalog/machine-types", json={"code": "LOCK", "name": "Lockstitch"})
    await admin.post("/catalog/machine-brands", json={"name": "Juki"})
    csv = (
        "asset_code,factory_code,machine_type,brand,model,serial,station_code,status\n"
        "M-IMP1,U2,Lockstitch,juki,DDL-9000C,SN1,L1-S01,active\n"
        "M-IMP2,U2,Unknown,Juki,,,,\n"
        "M-IMP3,U2,LOCK,Juki,,,L9-S99,\n"
    )
    d = (await admin.post("/import/machines?commit=true", files=upload(csv))).json()["data"]
    assert d["create"] == 1 and {e["column"] for e in d["errors"]} == {"machine_type", "station_code"}
    machines = (await admin.get("/machines?q=M-IMP")).json()["data"]
    assert [(m["asset_code"], m["machine_type"], m["station"]["code"]) for m in machines] == [("M-IMP1", "LOCK", "L1-S01")]

    csv = (
        "employee_code,factory_code,full_name,full_name_bn,rfid_card_id,joined_on,skills\n"
        "E-IMP1,U2,Rahima Import,রহিমা,CARD-IMP1,2024-03-01,\n"
        "E-IMP2,U2,Dup Card,,CARD-IMP1,,\n"
        "E-IMP3,U2,Bad Date,,,2024-13-01,\n"
        "E-IMP4,U2,Bad Skill,,,,NOPE:9\n"
    )
    d = (await admin.post("/import/workers?commit=true", files=upload(csv))).json()["data"]
    assert d["create"] == 1 and [e["column"] for e in d["errors"]] == ["rfid_card_id", "joined_on", "skills"]
    w = (await db.execute(select(Worker).where(Worker.employee_code == "E-IMP1"))).scalar_one()
    assert w.full_name_bn == "রহিমা" and w.rfid_card_id == "CARD-IMP1"


async def test_operations_and_needle_batches_import(admin):
    await admin.post("/catalog/machine-types", json={"code": "OVL", "name": "Overlock"})
    csv = (
        "product_code,product_name,style_no,operation_code,operation_name,operation_name_bn,smv,machine_type,count_unit,difficulty_group\n"
        "P-IMP,Tee,ST-1,OP-IMP1,Sleeve,হাতা,0.450,Overlock,One sleeve,B\n"
        "P-IMP,Tee,ST-1,OP-IMP2,Collar,,0.4501,Overlock,One collar,C\n"
        "P-IMP,Tee,ST-1,OP-IMP3,Collar,,0,Overlock,One collar,C\n"
    )
    d = (await admin.post("/import/operations?commit=true", files=upload(csv))).json()["data"]
    assert d["create"] == 1 and [e["row"] for e in d["errors"]] == [3, 4]
    ops = (await admin.get("/operations")).json()["data"]
    assert any(o["code"] == "OP-IMP1" and o["smv"] == 0.45 for o in ops)

    csv = (
        "supplier_name,brand,system,size_nm,point_type,lot_no,received_on,qty_received\n"
        "Supplier Imp,Organ,DBx1,90,SES,IMP-1,2026-10-02,20\n"
        "Supplier Imp,Organ,DBx1,ninety,SES,IMP-2,2026-10-02,20\n"
    )
    d = (await admin.post("/import/needle-batches?commit=true", files=upload(csv))).json()["data"]
    assert d["create"] == 1 and d["errors"][0]["column"] == "size_nm"


async def test_attendance_import_creates_rfid_tap_events(admin, db):
    assigned = (
        await db.execute(
            select(Worker)
            .join(WorkerAssignment, WorkerAssignment.worker_id == Worker.id)
            .where(WorkerAssignment.valid_to.is_(None))
            .limit(1)
        )
    ).scalar_one()
    unassigned = (
        await admin.post(
            "/workers", json={"factory_id": assigned.factory_id, "employee_code": "E-ATT0", "full_name": "No Station"}
        )
    ).json()["data"]
    csv = (
        "employee_code,card_id,punch_time,direction,device\n"
        f"{assigned.employee_code},,2026-11-17 07:52,in,Gate-1\n"
        f",{assigned.rfid_card_id},2026-11-17 17:04,out,Gate-1\n"
        f"{unassigned['employee_code']},,2026-11-17 07:55,in,Gate-1\n"
        f"{assigned.employee_code},,17/11/2026 08:00,in,\n"
        ",,2026-11-17 08:00,,\n"
    )
    d = (await admin.post("/import/attendance?commit=true", files=upload(csv))).json()["data"]
    assert d["create"] == 2, d
    assert [e["row"] for e in d["errors"]] == [4, 5, 6]
    assert "no active station" in d["errors"][0]["message"]
    rows = (
        (
            await db.execute(
                select(Event).where(Event.worker_id == assigned.id, Event.source == "import", Event.event_type == "rfid_tap")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2 and {e.state for e in rows} == {"tap"}
    assert min(e.start_time for e in rows).isoformat() == "2026-11-17T01:52:00+00:00"  # Asia/Dhaka is UTC+6
    again = (await admin.post("/import/attendance", files=upload(csv))).json()["data"]
    assert again["create"] == 0 and "already imported" in again["errors"][0]["message"]
    count = (
        await db.execute(select(func.count()).select_from(Event).where(Event.worker_id == assigned.id, Event.source == "import"))
    ).scalar_one()
    assert count == 2
