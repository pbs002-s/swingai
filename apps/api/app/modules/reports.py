"""Day reports for one line: workers' output and time, and machine downtime by station.

JSON for the on-screen report (which prints to PDF from the browser, so Bangla renders correctly) and CSV for
spreadsheets. Management and factory admins only, like the performance ranking. There is no rank here: a report
states what happened; ranking stays in /performance with its fairness rules.
"""

import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import ARRAY, DateTime, Integer, bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import not_found, ok
from app.core.security import check_line_scope, client_ip, require_roles
from app.models import Line, Station, User
from app.modules.performance import LOOKBACK, VIEWERS, _factory, _shift_versions, _work_windows, compute
from app.modules.shift import DEFAULT_THRESHOLDS, policy_body

router = APIRouter(tags=["reports"])
viewers = require_roles(*VIEWERS)
STATES = ("working", "idle", "phone_use", "away", "uncertain")

_DOWNTIME = text("""
with w as (select * from unnest(:ws, :we) as t(ws, we)),
ev as (
  select e.station_id, e.state, e.review_status, e.start_time,
    coalesce(lead(e.start_time) over (partition by e.station_id order by e.start_time, e.id), :now) as end_time
  from events e
  where e.event_type = 'machine_state' and e.start_time >= :lookback and e.start_time < :until
    and e.station_id = any(:stations)
)
select ev.station_id, count(distinct (ev.start_time, ev.station_id)) as stops,
  sum(extract(epoch from least(ev.end_time, w.we) - greatest(ev.start_time, w.ws))) / 60 as minutes
from ev join w on ev.start_time < w.we and ev.end_time > w.ws
where ev.state = 'stopped' and ev.review_status <> 'rejected' and ev.end_time - ev.start_time > :down
group by 1
""").bindparams(
    bindparam("ws", type_=ARRAY(DateTime(timezone=True))),
    bindparam("we", type_=ARRAY(DateTime(timezone=True))),
    bindparam("stations", type_=ARRAY(Integer)),
)


def day_bounds(tz_name: str, day: date, now: datetime) -> tuple[datetime, datetime]:
    """[start, end) of the factory's local day in UTC. A day still in progress ends now."""
    tz = ZoneInfo(tz_name)
    start = datetime.combine(day, time(0), tz)
    return start, min(datetime.combine(day + timedelta(days=1), time(0), tz), now)


def csv_cell(value: Any) -> Any:
    """Stop spreadsheet formulas: a text cell starting with = + - @ would run when the file is opened."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def to_csv(header: list[str], rows: list[list[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for r in rows:
        writer.writerow([csv_cell(v) for v in r])
    return "﻿" + out.getvalue()  # BOM so Excel reads Bangla names as UTF-8


async def build_day(db: AsyncSession, user: User, day: date, line_id: int) -> dict[str, Any]:
    line = await db.get(Line, line_id)
    if line is None:
        raise not_found("Line")
    check_line_scope(user, line_id)
    factory = await _factory(db)
    now = utcnow()
    since, until = day_bounds(factory.timezone, day, now)
    if until <= since:
        return _empty(day, factory.timezone, line)

    perf = await compute(db, user, None, None, line_id, since=since, until=until)
    workers = []
    for r in perf["rows"]:
        i = r["_inputs"]
        workers.append(
            {
                "worker": r["worker"],
                "operation": r["operation"]["name"],
                "accepted": i["accepted"],
                "rework": i["rework"],
                "rejected": i["rejected"],
                "efficiency_pct": r["efficiency_pct"],
                "first_pass_pct": r["first_pass_pct"],
                "scheduled_min": i["scheduled_min"],
                "attended_min": i["attended_min"],
                "downtime_min": i["downtime_min"],
                "coverage_pct": r["coverage_pct"],
                "state_min": {s: i["state_min"].get(s, 0.0) for s in STATES},
            }
        )
    workers.sort(key=lambda w: w["worker"]["name"])

    stations = list(
        (
            await db.execute(
                select(Station).where(Station.line_id == line_id, Station.status != "inactive").order_by(Station.position)
            )
        ).scalars()
    )
    down = await _downtime(db, factory.id, factory.timezone, [s.id for s in stations], since, until, now)
    station_rows = [
        {"code": s.code, "stops": down.get(s.id, (0, 0.0))[0], "down_min": down.get(s.id, (0, 0.0))[1]} for s in stations
    ]
    station_rows = [s for s in station_rows if s["stops"]]
    return {
        "date": day.isoformat(),
        "timezone": factory.timezone,
        "partial": until < datetime.combine(day + timedelta(days=1), time(0), ZoneInfo(factory.timezone)),
        "line": {"id": line.id, "code": line.code, "name": line.name},
        "generated_at": now.isoformat(),
        "workers": workers,
        "stations": station_rows,
        "totals": {
            "accepted": sum(w["accepted"] for w in workers),
            "rework": sum(w["rework"] for w in workers),
            "rejected": sum(w["rejected"] for w in workers),
            "stops": sum(s["stops"] for s in station_rows),
            "down_min": round(sum(s["down_min"] for s in station_rows), 1),
        },
    }


def _empty(day: date, tz: str, line: Line) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "timezone": tz,
        "partial": True,
        "line": {"id": line.id, "code": line.code, "name": line.name},
        "generated_at": utcnow().isoformat(),
        "workers": [],
        "stations": [],
        "totals": {"accepted": 0, "rework": 0, "rejected": 0, "stops": 0, "down_min": 0.0},
    }


async def _downtime(
    db: AsyncSession, factory_id: int, tz: str, station_ids: list[int], since: datetime, until: datetime, now: datetime
) -> dict[int, tuple[int, float]]:
    windows = _work_windows(await _shift_versions(db, factory_id), tz, since, until)
    if not station_ids or not windows:
        return {}
    th = await policy_body(db, factory_id, "thresholds", DEFAULT_THRESHOLDS)
    params = {
        "ws": [a for a, _ in windows],
        "we": [b for _, b in windows],
        "stations": station_ids,
        "now": now,
        "until": until,
        "lookback": since - LOOKBACK,
        "down": timedelta(minutes=float(th["down_after_min"])),
    }
    return {sid: (int(n), round(float(m or 0), 1)) for sid, n, m in (await db.execute(_DOWNTIME, params)).all()}


@router.get("/reports/day")
async def day_report(
    request: Request,
    day: date = Query(alias="date"),
    line_id: int = Query(),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(viewers),
):
    data = await build_day(db, user, day, line_id)
    audit(db, user.id, "report.view", "line", line_id, {"date": data["date"], "format": "json"}, client_ip(request))
    await db.commit()
    return ok(data)


@router.get("/reports/day.csv")
async def day_report_csv(
    request: Request,
    day: date = Query(alias="date"),
    line_id: int = Query(),
    section: str = Query(default="workers", pattern="^(workers|downtime)$"),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(viewers),
):
    d = await build_day(db, user, day, line_id)
    if section == "workers":
        header = [
            "date",
            "line",
            "worker_code",
            "worker",
            "operation",
            "accepted",
            "rework",
            "rejected",
            "efficiency_pct",
            "first_pass_pct",
            "scheduled_min",
            "attended_min",
            "machine_downtime_min",
            "coverage_pct",
            *[f"{s}_min" for s in STATES],
        ]
        rows = [
            [
                d["date"],
                d["line"]["code"],
                w["worker"]["code"],
                w["worker"]["name"],
                w["operation"],
                w["accepted"],
                w["rework"],
                w["rejected"],
                w["efficiency_pct"],
                w["first_pass_pct"],
                w["scheduled_min"],
                w["attended_min"],
                w["downtime_min"],
                w["coverage_pct"],
                *[w["state_min"][s] for s in STATES],
            ]
            for w in d["workers"]
        ]
    else:
        header = ["date", "line", "station", "stops", "downtime_min"]
        rows = [[d["date"], d["line"]["code"], s["code"], s["stops"], s["down_min"]] for s in d["stations"]]
    audit(db, user.id, "report.export", "line", line_id, {"date": d["date"], "section": section}, client_ip(request))
    await db.commit()
    name = f"{section}-{d['line']['code']}-{d['date']}.csv"
    return Response(
        to_csv(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
