"""Performance ranking: deterministic workers on one operation, yesterday's day shift (08:00-17:00, break 13-14)."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.db import utcnow
from app.core.security import hash_password
from app.main import app
from app.models import (
    Event,
    Floor,
    Line,
    Operation,
    Product,
    ProductionEntry,
    Station,
    User,
    UserRole,
    Worker,
    WorkerAssignment,
)
from app.modules import performance
from app.simulator.seed import DEMO_PASSWORD
from tests.conftest import login_as

if not any(getattr(r, "path", "") == "/api/v1/performance" for r in app.routes):
    app.include_router(performance.router, prefix="/api/v1")

TZ = ZoneInfo("Asia/Dhaka")
DEFAULT = {"production": 50, "quality": 35, "time": 15}
# name -> (accepted, rework, rejected, [(local HH:MM, state)])
PLAN = {
    "Ayesha P.": (480, 0, 0, [("08:00", "working"), ("13:00", "break"), ("14:00", "working"), ("17:00", "break")]),
    "Bina P.": (
        240,
        30,
        30,
        [
            ("08:00", "working"),
            ("10:00", "idle"),
            ("11:00", "working"),
            ("13:00", "break"),
            ("14:00", "working"),
            ("17:00", "break"),
        ],
    ),
    "Chaya P.": (
        360,
        0,
        0,
        [
            ("08:00", "working"),
            ("09:00", "phone_use"),
            ("10:00", "working"),
            ("13:00", "break"),
            ("14:00", "working"),
            ("17:00", "break"),
        ],
    ),
    "Dola P.": (400, 0, 0, [("08:00", "working"), ("09:00", "uncertain"), ("17:00", "break")]),
}


def _at(day: date, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), TZ)


@pytest.fixture(scope="session")
async def perf_data():
    from app.core.db import SessionLocal

    day = utcnow().astimezone(TZ).date() - timedelta(days=1)
    async with SessionLocal() as db:
        floor = (await db.execute(select(Floor).order_by(Floor.id).limit(1))).scalar_one()
        product = Product(code="P-PERF", name="Perf test")
        line = Line(floor_id=floor.id, code="LPERF", name="Perf line")
        other = Line(floor_id=floor.id, code="LPERF2", name="Perf other line")
        db.add_all([product, line, other])
        await db.flush()
        op = Operation(product_id=product.id, code="OP-PERF", name="Perf seam", smv=Decimal("1.000"), difficulty_group="Z")
        db.add(op)
        await db.flush()
        ids, phone_event = {}, None
        for n, (name, (acc, rew, rej, states)) in enumerate(PLAN.items()):
            st = Station(line_id=line.id, code=f"LPERF-S{n}", name=f"Perf {n}", position=n)
            w = Worker(factory_id=floor.factory_id, employee_code=f"E-PERF{n}", full_name=name)
            db.add_all([st, w])
            await db.flush()
            ids[name] = w.id
            db.add(
                WorkerAssignment(
                    worker_id=w.id, station_id=st.id, operation_id=op.id, valid_from=_at(day, "00:00") - timedelta(days=3)
                )
            )
            db.add(
                ProductionEntry(
                    worker_id=w.id,
                    station_id=st.id,
                    operation_id=op.id,
                    period_start=_at(day, "08:00"),
                    period_end=_at(day, "17:00"),
                    qty_accepted=acc,
                    qty_rework=rew,
                    qty_rejected=rej,
                    source="manual",
                    status="confirmed",
                )
            )
            for hhmm, state in states:
                e = Event(
                    event_uuid=uuid.uuid4(),
                    event_type="worker_state",
                    state=state,
                    station_id=st.id,
                    source="simulator",
                    start_time=_at(day, hhmm),
                    review_status="pending" if state == "phone_use" else "auto_accepted",
                    meta={},
                )
                db.add(e)
                if state == "phone_use":
                    phone_event = e
        db.add(User(email="perf-sup@stitchsense.local", full_name="Other line sup", password_hash=hash_password(DEMO_PASSWORD)))
        await db.flush()
        sup = (await db.execute(select(User).where(User.email == "perf-sup@stitchsense.local"))).scalar_one()
        db.add(UserRole(user_id=sup.id, role="management", scope_type="line", scope_id=other.id))
        await db.commit()
        return {"op": op.id, "ids": ids, "phone_event": phone_event.id, "line": line.id}


def _rows(resp) -> dict[str, dict]:
    assert resp.status_code == 200, resp.text
    return {r["worker"]["name"]: r for r in resp.json()["data"]["rows"]}


async def test_ranking_percentile_weights_coverage_and_rejected_minutes(admin, perf_data):
    assert (await admin.post("/performance/policy", json={"weights": DEFAULT, "min_coverage_pct": 80})).status_code == 200
    rv = await admin.post(f"/events/{perf_data['phone_event']}/review", json={"decision": "reject", "note": "drinking water"})
    assert rv.status_code == 200, rv.text

    resp = await admin.get(f"/performance?days=7&group={perf_data['op']}")
    body = resp.json()["data"]
    rows = _rows(resp)
    assert body["bonus_enabled"] is False and body["policy_version_id"]
    assert {"value": str(perf_data["op"]), "label": "Perf seam (group Z)"} in body["groups"]

    a, b, c, d = (rows[n] for n in PLAN)
    assert (a["efficiency_pct"], b["efficiency_pct"], c["efficiency_pct"]) == (100.0, 50.0, 75.0)
    assert (a["scores"]["production"], c["scores"]["production"], b["scores"]["production"]) == (100.0, 50.0, 0.0)
    assert b["first_pass_pct"] == 80.0 and b["productive_pct"] == 87.5
    # rejected phone-use hour is neither productive nor unproductive, only lowers coverage
    assert c["productive_pct"] == 100.0 and c["coverage_pct"] == 87.5
    assert (a["total"], c["total"], b["total"]) == (100.0, 75.0, 41.1)
    assert [a["rank"], c["rank"], b["rank"]] == [1, 2, 3]
    assert d["eligible"] is False and d["exclusion_reason"] == "insufficient data" and d["total"] is None and d["rank"] is None
    assert [r["worker"]["name"] for r in body["rows"]][:3] == ["Ayesha P.", "Chaya P.", "Bina P."]

    ex = (await admin.get(f"/performance/workers/{perf_data['ids']['Chaya P.']}?group={perf_data['op']}")).json()["data"]
    comps = {x["key"]: x for x in ex["components"]}
    assert comps["production"]["weight"] == 50 and comps["production"]["contribution"] == 25.0
    assert "360 accepted pieces × SMV 1" in comps["production"]["source"]
    assert "60 min phone use" in comps["time"]["source"] and ex["excluded"]["rejected_min"] == {"phone_use": 60.0}

    # weights applied: production only
    assert (
        await admin.post("/performance/policy", json={"weights": {"production": 100, "quality": 0, "time": 0}})
    ).status_code == 200
    rows = _rows(await admin.get(f"/performance?group={perf_data['op']}"))
    assert rows["Chaya P."]["total"] == 50.0 and rows["Bina P."]["total"] == 0.0
    assert (await admin.post("/performance/policy", json={"weights": DEFAULT})).status_code == 200


async def test_policy_versions_and_rejects_bad_weights(admin):
    before = (await admin.get("/performance/policy")).json()["data"]
    r = await admin.post("/performance/policy", json={"weights": {"production": 60, "quality": 30, "time": 10}})
    after = r.json()["data"]
    assert after["version"] == before["version"] + 1 and after["version_id"] != before["version_id"]
    assert (await admin.get("/performance/policy")).json()["data"]["weights"]["production"] == 60
    for bad in (
        {"production": 60, "quality": 30, "time": 20},
        {"production": 50.5, "quality": 34.5, "time": 15},
        {"production": 100},
    ):
        resp = await admin.post("/performance/policy", json={"weights": bad})
        assert resp.status_code == 422 and resp.json()["error"]["code"] == "POLICY_WEIGHTS_INVALID"
    await admin.post("/performance/policy", json={"weights": DEFAULT})


async def test_roles_and_line_scope(supervisor, manager, perf_data):
    assert (await manager.get("/performance")).status_code == 200
    assert len(_rows(await manager.get(f"/performance?group={perf_data['op']}"))) == 4
    assert (await supervisor.get("/performance")).status_code == 403  # rankings are for management, not supervisors
    assert (await supervisor.post("/performance/policy", json={"weights": DEFAULT})).status_code == 403
    assert (await manager.post("/performance/policy", json={"weights": DEFAULT})).status_code == 403
    quality = await login_as("quality@stitchsense.local")
    assert (await quality.get("/performance")).status_code == 403
    await quality.aclose()
    scoped = await login_as("perf-sup@stitchsense.local")
    assert _rows(await scoped.get(f"/performance?group={perf_data['op']}")) == {}
    assert (await scoped.get(f"/performance?line_id={perf_data['line']}")).status_code == 403
    await scoped.aclose()


def test_each_day_uses_the_shift_version_in_force_that_day():
    from datetime import UTC

    from app.modules.performance import _shift_at

    day = {"start": "08:00", "end": "17:00"}
    night = {"start": "21:00", "end": "06:00", "crosses_midnight": True}
    d = lambda n: datetime(2026, 11, n, tzinfo=UTC)  # noqa: E731
    versions = [(d(1), d(10), day), (d(10), None, night)]
    assert _shift_at(versions, d(5))["start"] == "08:00"  # history keeps its own schedule
    assert _shift_at(versions, d(12))["start"] == "21:00"
    assert _shift_at(versions, datetime(2026, 10, 1, tzinfo=UTC))["start"] == "08:00"  # before any version
    assert _shift_at([], d(5))["start"]  # no policy at all: the default shift


async def test_day_report_and_csv(manager, supervisor, perf_data):
    day = (utcnow().astimezone(TZ).date() - timedelta(days=1)).isoformat()
    r = await manager.get(f"/reports/day?date={day}&line_id={perf_data['line']}")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert [w["worker"]["name"] for w in d["workers"]] == sorted(PLAN)  # a report lists people alphabetically, never ranked
    assert d["totals"]["accepted"] == sum(v[0] for v in PLAN.values()) and d["partial"] is False
    assert all(not k.endswith("rank") for k in d["workers"][0])

    csv_resp = await manager.get(f"/reports/day.csv?date={day}&line_id={perf_data['line']}")
    assert csv_resp.status_code == 200 and csv_resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_resp.headers["content-disposition"] and "Ayesha P." in csv_resp.text
    assert (await manager.get(f"/reports/day.csv?date={day}&line_id={perf_data['line']}&section=downtime")).status_code == 200

    assert (await supervisor.get(f"/reports/day?date={day}&line_id={perf_data['line']}")).status_code == 403
    assert (await manager.get(f"/reports/day?date={day}&line_id=999999")).status_code == 404
    assert (await manager.get(f"/reports/day?date=not-a-date&line_id={perf_data["line"]}")).status_code == 400


def test_csv_cells_cannot_run_formulas():
    from app.modules.reports import csv_cell, to_csv

    assert csv_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and csv_cell("@x") == "'@x" and csv_cell(5) == 5
    assert to_csv(["a"], [["+1+1"]]).startswith("﻿") and "'+1+1" in to_csv(["a"], [["+1+1"]])
