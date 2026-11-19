"""Policies with history (PRD F-POL-6): shift, thresholds and retention. A change is a new version, never an edit.

The performance ranking policy keeps its own endpoints in `performance.py`. New versions can start now or at a
later time; a scheduled version closes the current one when it starts, so history stays exact.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, ok
from app.core.security import client_ip, require_roles
from app.models import Factory, Policy, PolicyVersion, User
from app.modules.shift import DEFAULT_SHIFT, DEFAULT_THRESHOLDS

router = APIRouter(tags=["policies"])
Kind = Literal["shift", "thresholds", "retention"]
NAMES = {"shift": "Shift", "thresholds": "Floor thresholds", "retention": "Data retention"}
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
MAX_SHIFT_MIN = 16 * 60
DAY_MIN = 1440


def _min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


class BreakIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM)


class ShiftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM)
    crosses_midnight: bool = False
    breaks: list[BreakIn] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _consistent(self) -> "ShiftBody":
        s, e = _min(self.start), _min(self.end)
        length = (e - s) % DAY_MIN
        if self.crosses_midnight != (e <= s):
            raise ValueError("crosses_midnight must be on exactly when the end time is not later than the start time")
        if length == 0 or length > MAX_SHIFT_MIN:
            raise ValueError("a shift must be longer than 0 and at most 16 hours")
        spans = sorted(((_min(b.start) - s) % DAY_MIN, (_min(b.end) - s) % DAY_MIN) for b in self.breaks)
        end_of_prev = 0
        for b0, b1 in spans:
            if not (end_of_prev <= b0 < b1 <= length):
                raise ValueError("breaks must sit inside the shift, end after they start, and not overlap")
            end_of_prev = b1
        return self


class ThresholdsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_efficiency_pct: float = Field(ge=1, le=200)
    down_after_min: float = Field(ge=1, le=240)
    idle_after_min: float = Field(ge=1, le=240)


class RetentionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events_days: int = Field(ge=30, le=3650)  # raw activity events
    audit_days: int = Field(ge=365, le=3650)  # the audit log is kept longer than activity data


MODELS: dict[str, type[BaseModel]] = {"shift": ShiftBody, "thresholds": ThresholdsBody, "retention": RetentionBody}
DEFAULTS: dict[str, dict[str, Any]] = {
    "shift": DEFAULT_SHIFT,
    "thresholds": DEFAULT_THRESHOLDS,
    "retention": {"events_days": 365, "audit_days": 730},
}


class NewVersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: dict[str, Any]
    effective_from: datetime | None = None
    note: str | None = Field(default=None, max_length=200)


def _version_out(v: PolicyVersion) -> dict[str, Any]:
    return {
        "version": v.version,
        "body": v.body,
        "effective_from": v.effective_from.isoformat(),
        "effective_to": v.effective_to.isoformat() if v.effective_to else None,
        "created_by": v.created_by,
    }


async def _factory(db: AsyncSession) -> Factory:
    return (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one()


async def _policy(db: AsyncSession, factory_id: int, kind: str) -> Policy | None:
    return (await db.execute(select(Policy).where(Policy.factory_id == factory_id, Policy.kind == kind))).scalar_one_or_none()


async def _versions(db: AsyncSession, policy_id: int) -> list[PolicyVersion]:
    q = select(PolicyVersion).where(PolicyVersion.policy_id == policy_id).order_by(PolicyVersion.version.desc())
    return list((await db.execute(q)).scalars())


@router.get("/policies")
async def list_policies(db: AsyncSession = Depends(get_session), _: User = Depends(require_roles("factory_admin", "management"))):
    factory, now, out = await _factory(db), utcnow(), []
    for kind in MODELS:
        policy = await _policy(db, factory.id, kind)
        versions = await _versions(db, policy.id) if policy else []
        current = next(
            (v for v in versions if v.effective_from <= now and (v.effective_to is None or v.effective_to > now)), None
        )
        scheduled = next((v for v in versions if v.effective_from > now), None)
        out.append(
            {
                "kind": kind,
                "name": NAMES[kind],
                "current": _version_out(current) if current else {"version": 0, "body": DEFAULTS[kind], "default": True},
                "scheduled": _version_out(scheduled) if scheduled else None,
                "history": [_version_out(v) for v in versions],
                "schema": MODELS[kind].model_json_schema(),
            }
        )
    return ok(out)


@router.post("/policies/{kind}", status_code=201)
async def new_version(
    kind: Kind,
    body: NewVersionIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    try:
        clean = MODELS[kind].model_validate(body.body).model_dump()
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first["loc"])
        raise AppError(
            422, "POLICY_INVALID", f"{field + ': ' if field else ''}{first['msg'].removeprefix('Value error, ')}"
        ) from None
    now = utcnow()
    start = body.effective_from or now
    if start < now.replace(microsecond=0) and body.effective_from is not None:
        raise AppError(422, "POLICY_IN_PAST", "A new version cannot start in the past: history is never rewritten.")
    start = max(start, now)

    factory = await _factory(db)
    policy = await _policy(db, factory.id, kind)
    if policy is None:
        policy = Policy(factory_id=factory.id, kind=kind, name=NAMES[kind])
        db.add(policy)
        await db.flush()
    versions = await _versions(db, policy.id)
    if versions and versions[0].effective_from > now:
        raise AppError(409, "POLICY_ALREADY_SCHEDULED", "A change is already scheduled. Wait for it to start first.")
    latest = versions[0] if versions else None
    if latest is not None:
        if latest.effective_to is None or latest.effective_to > start:
            latest.effective_to = start
    pv = PolicyVersion(
        policy_id=policy.id,
        version=(latest.version + 1) if latest else 1,
        body=clean,
        effective_from=start,
        created_by=user.id,
    )
    db.add(pv)
    await db.flush()
    audit(
        db,
        user.id,
        f"policy.{kind}.version",
        "policy_version",
        pv.id,
        {
            "version": pv.version,
            "from": latest.version if latest else None,
            "effective_from": start.isoformat(),
            "note": body.note,
        },
        client_ip(request),
    )
    await db.commit()
    return ok(_version_out(pv))


@router.get("/policies/schema/{kind}")
async def policy_schema(kind: Kind, _: User = Depends(require_roles("factory_admin", "management"))):
    return ok(MODELS[kind].model_json_schema())
