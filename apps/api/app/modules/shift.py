"""Shift windows from the factory's versioned shift policy."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.models import Factory, Policy, PolicyVersion

DEFAULT_SHIFT: dict[str, Any] = {
    "start": "08:00",
    "end": "17:00",
    "crosses_midnight": False,
    "breaks": [{"start": "13:00", "end": "14:00"}],
}
DEFAULT_THRESHOLDS: dict[str, Any] = {"target_efficiency_pct": 70, "down_after_min": 5, "idle_after_min": 5}


@dataclass(frozen=True)
class ShiftWindow:
    start: datetime
    end: datetime
    breaks: tuple[tuple[datetime, datetime], ...]
    tz: ZoneInfo

    def worked_minutes(self, until: datetime) -> float:
        """Scheduled working minutes from shift start to `until`, breaks excluded."""
        until = min(max(until, self.start), self.end)
        total = (until - self.start).total_seconds() / 60
        for b0, b1 in self.breaks:
            overlap = (min(until, b1) - max(self.start, b0)).total_seconds() / 60
            total -= max(0.0, overlap)
        return max(0.0, total)

    def in_break(self, at: datetime) -> bool:
        return any(b0 <= at < b1 for b0, b1 in self.breaks)


async def policy_body(db: AsyncSession, factory_id: int, kind: str, default: dict[str, Any]) -> dict[str, Any]:
    now = utcnow()
    q = (
        select(PolicyVersion.body)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(
            Policy.factory_id == factory_id,
            Policy.kind == kind,
            PolicyVersion.effective_from <= now,
            or_(PolicyVersion.effective_to.is_(None), PolicyVersion.effective_to > now),
        )
        .order_by(PolicyVersion.effective_from.desc())
        .limit(1)
    )
    body = (await db.execute(q)).scalar_one_or_none()
    return {**default, **(body or {})}


def _at(day: date, hhmm: str, tz: ZoneInfo) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), tz).astimezone(UTC)


def window_for(body: dict[str, Any], tz_name: str, now: datetime | None = None) -> ShiftWindow:
    """The shift that contains `now`, else today's shift (shift date = the date it starts)."""
    tz = ZoneInfo(tz_name)
    now = now or utcnow()
    today = now.astimezone(tz).date()
    crosses = bool(body.get("crosses_midnight"))

    def build(day: date) -> ShiftWindow:
        start = _at(day, body["start"], tz)
        end = _at(day + timedelta(days=1) if crosses else day, body["end"], tz)
        breaks = []
        for b in body.get("breaks", []):
            b0 = _at(day, b["start"], tz)
            b0 = b0 + timedelta(days=1) if b0 < start else b0
            b1 = _at(day, b["end"], tz)
            b1 = b1 + timedelta(days=1) if b1 <= b0 else b1
            breaks.append((b0, b1))
        return ShiftWindow(start, end, tuple(breaks), tz)

    if crosses:
        yesterday = build(today - timedelta(days=1))
        if yesterday.start <= now < yesterday.end:
            return yesterday
    return build(today)


async def current_shift(db: AsyncSession, factory: Factory) -> ShiftWindow:
    return window_for(await policy_body(db, factory.id, "shift", DEFAULT_SHIFT), factory.timezone)
