"""Policy versions: validated, versioned, never rewritten."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.core.db import utcnow
from app.models import Policy, PolicyVersion

SHIFT = {"start": "08:00", "end": "17:00", "crosses_midnight": False, "breaks": [{"start": "13:00", "end": "14:00"}]}


@pytest.fixture
async def clean_retention(db):
    async def wipe():
        ids = (await db.execute(select(Policy.id).where(Policy.kind == "retention"))).scalars().all()
        if ids:
            await db.execute(delete(PolicyVersion).where(PolicyVersion.policy_id.in_(ids)))
            await db.execute(delete(Policy).where(Policy.id.in_(ids)))
            await db.commit()

    await wipe()
    yield
    await wipe()


@pytest.mark.parametrize(
    "kind,body,fragment",
    [
        ("shift", {**SHIFT, "end": "07:00"}, "crosses_midnight"),  # ends before it starts but is not marked overnight
        ("shift", {**SHIFT, "breaks": [{"start": "07:00", "end": "08:30"}]}, "inside the shift"),
        ("shift", {**SHIFT, "breaks": [{"start": "12:00", "end": "13:30"}, {"start": "13:00", "end": "14:00"}]}, "overlap"),
        ("shift", {**SHIFT, "start": "6:00"}, "start"),
        ("thresholds", {"target_efficiency_pct": 70, "down_after_min": 0, "idle_after_min": 5}, "down_after_min"),
        ("retention", {"events_days": 5, "audit_days": 730}, "events_days"),
        ("retention", {"events_days": 365, "audit_days": 730, "extra": 1}, "extra"),
    ],
)
async def test_invalid_policies_are_rejected_with_a_reason(admin, kind, body, fragment):
    r = await admin.post(f"/policies/{kind}", json={"body": body})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "POLICY_INVALID" and fragment in r.json()["error"]["message"]


async def test_night_shift_is_valid(admin, db, clean_retention):
    # validate only: the schema accepts a 22:00-06:00 shift with a break after midnight
    from app.modules.policies import ShiftBody

    ShiftBody.model_validate({"start": "22:00", "end": "06:00", "crosses_midnight": True, "breaks": [{"start": "01:00", "end": "01:30"}]})


async def test_versions_chain_and_history_is_kept(admin, supervisor, clean_retention):
    first = (await admin.post("/policies/retention", json={"body": {"events_days": 365, "audit_days": 730}})).json()["data"]
    assert first["version"] == 1 and first["effective_to"] is None
    second = (await admin.post("/policies/retention", json={"body": {"events_days": 180, "audit_days": 730}, "note": "shorter"})).json()
    assert second["data"]["version"] == 2

    listing = {p["kind"]: p for p in (await admin.get("/policies")).json()["data"]}["retention"]
    assert listing["current"]["version"] == 2 and listing["current"]["body"]["events_days"] == 180
    history = {h["version"]: h for h in listing["history"]}
    assert history[1]["effective_to"] == history[2]["effective_from"]  # the old version closes exactly when the new one starts
    assert "events_days" in listing["schema"]["properties"]

    assert (await supervisor.post("/policies/retention", json={"body": {"events_days": 365, "audit_days": 730}})).status_code == 403
    assert (await supervisor.get("/policies")).status_code == 403


async def test_a_change_can_be_scheduled_once_and_not_in_the_past(admin, clean_retention):
    await admin.post("/policies/retention", json={"body": {"events_days": 365, "audit_days": 730}})
    past = (utcnow() - timedelta(days=1)).isoformat()
    r = await admin.post("/policies/retention", json={"body": {"events_days": 200, "audit_days": 730}, "effective_from": past})
    assert r.json()["error"]["code"] == "POLICY_IN_PAST"

    later = (utcnow() + timedelta(days=2)).isoformat()
    assert (await admin.post("/policies/retention", json={"body": {"events_days": 200, "audit_days": 730}, "effective_from": later})).status_code == 201
    listing = {p["kind"]: p for p in (await admin.get("/policies")).json()["data"]}["retention"]
    assert listing["current"]["version"] == 1 and listing["scheduled"]["version"] == 2  # still version 1 until it starts
    again = await admin.post("/policies/retention", json={"body": {"events_days": 100, "audit_days": 730}})
    assert again.json()["error"]["code"] == "POLICY_ALREADY_SCHEDULED"
