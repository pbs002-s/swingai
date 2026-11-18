"""Fair performance ranking with explanations (PRD §6.11 F-PERF-1..4, §7.3; BACKEND_DESIGN §4.4).

Computed on read from raw rows; nothing is stored yet (performance_snapshots come with R4 jobs).
Bonus and training suggestions stay off until pilot data is validated (PRD §11).

Definitions, per worker, over the factory's scheduled work windows in the period
(each shift day's start→end minus breaks, clipped to [now - days, now]):

* attended minutes = work-window minutes of the shift days on which the worker logged production,
  minus long machine stops (machine_state 'stopped' longer than thresholds.down_after_min) at their station.
  We use the shift schedule instead of summing production periods because hourly entries miss hours where
  nothing was booked, which would overstate efficiency.
* efficiency % = Σ(qty_accepted × operation SMV) / attended minutes × 100
* first pass % = accepted / (accepted + rework + rejected) × 100
* productive % = working / (working + idle + away + phone_use + uncertain) minutes, from worker_state
  transitions (each lasts until the station's next transition). Events whose review is 'rejected' are not
  counted at all; reclassified events count as their reviewed state.
* coverage % = minutes with a known worker_state (not uncertain, not rejected) / scheduled minutes.

Scores: production = percentile rank of efficiency within the comparison group (eligible workers only),
quality = first pass %, time = productive %. Total = Σ score × weight / 100.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import ARRAY, DateTime, Integer, bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import check_line_scope, client_ip, require_roles
from app.models import Factory, Operation, Policy, PolicyVersion, ProductionEntry, Station, User, Worker
from app.modules.shift import DEFAULT_SHIFT, DEFAULT_THRESHOLDS, ShiftWindow, policy_body, window_for

router = APIRouter(tags=["performance"])
VIEWERS = ("management", "factory_admin")  # rankings are sensitive: management reviews them, supervisors do not (PRD §5)
COMPONENTS = ("production", "quality", "time")
DEFAULT_RANKING: dict[str, Any] = {
    "weights": {"production": 50, "quality": 35, "time": 15},
    "min_coverage_pct": 80,
    "period_days": 7,
}
TIME_STATES = ("working", "idle", "away", "phone_use", "uncertain")
LOOKBACK = timedelta(days=1)  # ponytail: a transition older than this before the period is not seen; widen if shifts idle longer


# ---------- policy ----------


async def _factory(db: AsyncSession) -> Factory:
    f = (await db.execute(select(Factory).order_by(Factory.id).limit(1))).scalar_one_or_none()
    if f is None:
        raise not_found("Factory")
    return f


async def _current_version(db: AsyncSession, factory_id: int) -> PolicyVersion | None:
    now = utcnow()
    q = (
        select(PolicyVersion)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(Policy.factory_id == factory_id, Policy.kind == "ranking", PolicyVersion.effective_from <= now)
        .where((PolicyVersion.effective_to.is_(None)) | (PolicyVersion.effective_to > now))
        .order_by(PolicyVersion.effective_from.desc(), PolicyVersion.id.desc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


def _policy_out(pv: PolicyVersion | None) -> dict[str, Any]:
    body = {**DEFAULT_RANKING, **(pv.body if pv else {})}
    return {
        "version_id": pv.id if pv else None,
        "version": pv.version if pv else 0,
        "effective_from": pv.effective_from.isoformat() if pv else None,
        **body,
    }


class PolicyIn(BaseModel):
    weights: dict[str, Any]
    min_coverage_pct: int | None = Field(default=None, ge=0, le=100)
    period_days: int | None = Field(default=None, ge=1, le=90)


def _check_weights(w: dict[str, Any]) -> dict[str, int]:
    valid = (
        set(w) == set(COMPONENTS)
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in w.values())
        and sum(w.values()) == 100
    )
    if not valid:
        raise AppError(
            422,
            "POLICY_WEIGHTS_INVALID",
            "Weights must be whole numbers for production, quality and time that add up to 100.",
            {"weights": w},
        )
    return {k: int(w[k]) for k in COMPONENTS}


@router.get("/performance/policy")
async def get_policy(db: AsyncSession = Depends(get_session), _: User = Depends(require_roles(*VIEWERS))):
    return ok(_policy_out(await _current_version(db, (await _factory(db)).id)))


@router.post("/performance/policy")
async def set_policy(
    body: PolicyIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("factory_admin")),
):
    weights = _check_weights(body.weights)
    factory = await _factory(db)
    current = await _current_version(db, factory.id)
    old = _policy_out(current)
    policy = await db.get(Policy, current.policy_id) if current else None
    if policy is None:
        policy = Policy(factory_id=factory.id, kind="ranking", name="Performance ranking")
        db.add(policy)
        await db.flush()
    last = (await db.execute(select(func.max(PolicyVersion.version)).where(PolicyVersion.policy_id == policy.id))).scalar()
    now = utcnow()
    if current:
        current.effective_to = now
    new_body = {
        "weights": weights,
        "min_coverage_pct": body.min_coverage_pct if body.min_coverage_pct is not None else old["min_coverage_pct"],
        "period_days": body.period_days if body.period_days is not None else old["period_days"],
    }
    pv = PolicyVersion(policy_id=policy.id, version=(last or 0) + 1, body=new_body, effective_from=now, created_by=user.id)
    db.add(pv)
    await db.flush()
    audit(
        db, user.id, "policy.ranking.version", "policy_version", pv.id, {"from": old["version"], **new_body}, client_ip(request)
    )
    await db.commit()
    return ok(_policy_out(pv))


# ---------- period windows ----------


def _work_windows(shift_body: dict[str, Any], tz_name: str, since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
    """Scheduled working intervals (breaks removed) of every shift overlapping [since, until], clipped to it."""
    tz, out = ZoneInfo(tz_name), []
    day = since.astimezone(tz).date() - timedelta(days=1)
    while day <= until.astimezone(tz).date():
        sw: ShiftWindow = window_for(shift_body, tz_name, datetime.combine(day, time(12), tz))
        cursor = sw.start
        for b0, b1 in sorted(sw.breaks) + [(sw.end, sw.end)]:
            a, b = max(cursor, since), min(b0, until)
            if b > a:
                out.append((a, b))
            cursor = max(cursor, b1)
        day += timedelta(days=1)
    return out


# ---------- aggregation (3 grouped queries, independent of worker count) ----------

_SEGMENTS = text("""
with w as (select * from unnest(:ws, :we, :wd) as t(ws, we, day)),
ev as (
  select e.event_type, e.review_status,
    coalesce(e.worker_id, (select wa.worker_id from worker_assignments wa
       where wa.station_id = e.station_id and wa.valid_from <= e.start_time
         and (wa.valid_to is null or wa.valid_to > e.start_time)
       order by wa.valid_from desc limit 1)) as worker_id,
    case when e.review_status = 'reclassified' then coalesce((select r.new_state from event_reviews r
       where r.event_id = e.id and r.decision = 'reclassify' order by r.reviewed_at desc, r.id desc limit 1), e.state)
     else e.state end as state,
    e.start_time,
    coalesce(lead(e.start_time) over (partition by e.station_id, e.event_type order by e.start_time, e.id), :now) as end_time
  from events e
  where e.event_type in ('worker_state', 'machine_state') and e.start_time >= :lookback and e.start_time < :now
)
select ev.worker_id, w.day, ev.event_type, ev.state, ev.review_status = 'rejected' as rejected,
  sum(extract(epoch from least(ev.end_time, w.we) - greatest(ev.start_time, w.ws))) / 60 as minutes
from ev join w on ev.start_time < w.we and ev.end_time > w.ws
where ev.worker_id = any(:workers)
  and (ev.event_type = 'worker_state'
       or (ev.state = 'stopped' and ev.review_status <> 'rejected' and ev.end_time - ev.start_time > :down))
group by 1, 2, 3, 4, 5
""").bindparams(
    bindparam("ws", type_=ARRAY(DateTime(timezone=True))),
    bindparam("we", type_=ARRAY(DateTime(timezone=True))),
    bindparam("wd", type_=ARRAY(Integer)),
    bindparam("workers", type_=ARRAY(Integer)),
)

_DAYS = text("""
select distinct pe.worker_id, w.day
from production_entries pe join unnest(:ws, :we, :wd) as w(ws, we, day) on pe.period_start < w.we and pe.period_end > w.ws
where pe.worker_id = any(:workers)
""").bindparams(
    bindparam("ws", type_=ARRAY(DateTime(timezone=True))),
    bindparam("we", type_=ARRAY(DateTime(timezone=True))),
    bindparam("wd", type_=ARRAY(Integer)),
    bindparam("workers", type_=ARRAY(Integer)),
)


def _scope(user: User, line_id: int | None) -> set[int] | None:
    """Line ids the user may see (None = all)."""
    if line_id is not None:
        check_line_scope(user, line_id)
        return {line_id}
    if any(r.role == "system_admin" or (r.role in VIEWERS and r.scope_type in ("all", "factory")) for r in user.roles):
        return None
    return {r.scope_id for r in user.roles if r.role in VIEWERS and r.scope_type == "line" and r.scope_id is not None}


async def _production(db: AsyncSession, since: datetime, until: datetime, lines: set[int] | None, op_id: int | None):
    q = (
        select(
            ProductionEntry.worker_id,
            Operation.id,
            Operation.name,
            Operation.difficulty_group,
            Operation.smv,
            func.sum(ProductionEntry.qty_accepted),
            func.sum(ProductionEntry.qty_rework),
            func.sum(ProductionEntry.qty_rejected),
            func.min(Station.line_id),
        )
        .join(Operation, Operation.id == ProductionEntry.operation_id)
        .join(Station, Station.id == ProductionEntry.station_id)
        .where(ProductionEntry.worker_id.is_not(None), ProductionEntry.period_end > since, ProductionEntry.period_start < until)
        .group_by(ProductionEntry.worker_id, Operation.id)
    )
    if lines is not None:
        q = q.where(Station.line_id.in_(lines))
    if op_id is not None:
        q = q.where(Operation.id == op_id)
    return (await db.execute(q)).all()


def _pct(num: float, den: float) -> float | None:
    return round(num / den * 100, 1) if den > 0 else None


def _percentile(value: float, values: list[float]) -> float:
    """Share of the other group members strictly below `value` (lowest 0, highest 100, alone 100)."""
    if len(values) <= 1:
        return 100.0
    return round(sum(v < value for v in values) / (len(values) - 1) * 100, 1)


async def compute(db: AsyncSession, user: User, days: int | None, group: str | None, line_id: int | None) -> dict[str, Any]:
    factory = await _factory(db)
    pv = await _current_version(db, factory.id)
    policy = _policy_out(pv)
    weights: dict[str, int] = policy["weights"]
    days = days or int(policy["period_days"])
    until = utcnow()
    since = until - timedelta(days=days)
    op_id = int(group) if group and group.isdigit() else None
    prod = await _production(db, since, until, _scope(user, line_id), op_id)

    workers: dict[int, dict[str, Any]] = {}
    for wid, oid, oname, grp, smv, acc, rew, rej, lid in prod:
        w = workers.setdefault(wid, {"ops": [], "accepted": 0, "rework": 0, "rejected": 0, "earned": 0.0, "line_id": lid})
        earned = int(acc or 0) * float(smv)
        w["ops"].append({"id": oid, "name": oname, "group": grp, "smv": float(smv), "earned": earned})
        w["accepted"] += int(acc or 0)
        w["rework"] += int(rew or 0)
        w["rejected"] += int(rej or 0)
        w["earned"] += earned
    groups = sorted({(o["group"], o["id"], o["name"]) for w in workers.values() for o in w["ops"]})
    group_list = [{"value": g, "label": f"Group {g}"} for g in sorted({g for g, _, _ in groups})]
    group_list += [{"value": str(i), "label": f"{n} (group {g})"} for g, i, n in groups]
    if group and op_id is None:
        workers = {k: v for k, v in workers.items() if max(v["ops"], key=lambda o: o["earned"])["group"] == group}

    ids = list(workers)
    windows = _work_windows(await policy_body(db, factory.id, "shift", DEFAULT_SHIFT), factory.timezone, since, until)
    th = await policy_body(db, factory.id, "thresholds", DEFAULT_THRESHOLDS)
    day_of, day_min = [], defaultdict(float)
    for a, b in windows:
        d = a.astimezone(ZoneInfo(factory.timezone)).toordinal()
        day_of.append(d)
        day_min[d] += (b - a).total_seconds() / 60
    params = {"ws": [a for a, _ in windows], "we": [b for _, b in windows], "wd": day_of, "workers": ids}
    attended_days: dict[int, set[int]] = defaultdict(set)
    seg: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"states": defaultdict(float), "rejected": defaultdict(float), "down": 0.0}
    )
    if ids and windows:
        for wid, d in (await db.execute(_DAYS, params)).all():
            attended_days[wid].add(d)
        seg_params = {
            **params,
            "now": until,
            "lookback": since - LOOKBACK,
            "down": timedelta(minutes=float(th["down_after_min"])),
        }
        for wid, d, etype, state, rejected, minutes in (await db.execute(_SEGMENTS, seg_params)).all():
            if d not in attended_days[wid]:
                continue  # only shift days the worker attended count towards scheduled/known minutes
            s, m = seg[wid], float(minutes or 0)
            if etype == "machine_state":
                s["down"] += m
            elif rejected:
                s["rejected"][state] += m
            else:
                s["states"][state] += m

    names = {w.id: w for w in (await db.execute(select(Worker).where(Worker.id.in_(ids)))).scalars()} if ids else {}
    rows = [
        _row(wid, w, names.get(wid), seg[wid], sum(day_min[d] for d in attended_days[wid]), op_id) for wid, w in workers.items()
    ]
    _score(rows, weights, float(policy["min_coverage_pct"]))
    rows.sort(key=lambda r: (r["total"] is None, -(r["total"] or 0), r["worker"]["name"]))
    return {
        "period": {"days": days, "start": since.isoformat(), "end": until.isoformat()},
        "policy": policy,
        "policy_version_id": policy["version_id"],
        "group": group,
        "groups": group_list,
        "bonus_enabled": False,
        "training_enabled": False,
        "rows": rows,
    }


def _row(wid: int, w: dict[str, Any], person: Worker | None, s: dict[str, Any], scheduled: float, op_id: int | None):
    main = max(w["ops"], key=lambda o: o["earned"])
    st = s["states"]
    attended = max(0.0, scheduled - s["down"])
    time_den = sum(st[k] for k in TIME_STATES)
    known = sum(v for k, v in st.items() if k != "uncertain")
    inspected = w["accepted"] + w["rework"] + w["rejected"]
    return {
        "worker": {
            "id": wid,
            "name": person.full_name if person else f"#{wid}",
            "code": person.employee_code if person else None,
        },
        "operation": {"id": main["id"], "name": main["name"], "smv": main["smv"]},
        "line_id": w["line_id"],
        "comparison_group": f"op:{op_id}" if op_id else main["group"],
        "efficiency_pct": _pct(w["earned"], attended),
        "first_pass_pct": _pct(w["accepted"], inspected),
        "productive_pct": _pct(st["working"], time_den),
        "coverage_pct": _pct(known, scheduled) or 0.0,
        "_inputs": {
            "ops": w["ops"],
            "accepted": w["accepted"],
            "rework": w["rework"],
            "rejected": w["rejected"],
            "earned_min": round(w["earned"], 1),
            "scheduled_min": round(scheduled, 1),
            "attended_min": round(attended, 1),
            "downtime_min": round(s["down"], 1),
            "state_min": {k: round(v, 1) for k, v in st.items()},
            "rejected_min": {k: round(v, 1) for k, v in s["rejected"].items()},
        },
    }


def _score(rows: list[dict[str, Any]], weights: dict[str, int], min_cov: float) -> None:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        r["eligible"] = r["coverage_pct"] >= min_cov and r["efficiency_pct"] is not None
        r["exclusion_reason"] = None if r["eligible"] else "insufficient data"
        r["scores"] = r["contributions"] = r["total"] = r["rank"] = None
        if r["eligible"]:
            by_group[r["comparison_group"]].append(r)
    for members in by_group.values():
        effs = [r["efficiency_pct"] for r in members]
        for r in members:
            r["scores"] = {
                "production": _percentile(r["efficiency_pct"], effs),
                "quality": r["first_pass_pct"] or 0.0,
                "time": r["productive_pct"] or 0.0,
            }
            r["contributions"] = {k: round(r["scores"][k] * weights[k] / 100, 1) for k in COMPONENTS}
            r["total"] = round(sum(r["scores"][k] * weights[k] / 100 for k in COMPONENTS), 1)
            r["group_size"] = len(members)
        for i, r in enumerate(sorted(members, key=lambda r: -r["total"]), 1):
            r["rank"] = i


def _public(r: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in r.items() if not k.startswith("_")}


@router.get("/performance")
async def ranking(
    days: int | None = Query(default=None, ge=1, le=90),
    group: str | None = Query(default=None, max_length=32),
    line_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(*VIEWERS)),
):
    out = await compute(db, user, days, group, line_id)
    out["rows"] = [_public(r) for r in out["rows"]]
    return ok(out)


def _explain(r: dict[str, Any], weights: dict[str, int]) -> list[dict[str, Any]]:
    i, sc, ct = r["_inputs"], r["scores"] or {}, r["contributions"] or {}
    smv = f"SMV {i['ops'][0]['smv']:g}" if len(i["ops"]) == 1 else "each operation's SMV"
    st, rej = i["state_min"], i["rejected_min"]
    time_den = sum(st.get(k, 0.0) for k in TIME_STATES)
    rejected_txt = ", ".join(f"{v:g} min {k.replace('_', ' ')}" for k, v in rej.items() if v) or "none"
    rank_txt = f" Ranked against {r.get('group_size', 0)} workers in group {r['comparison_group']}." if r["eligible"] else ""
    return [
        {
            "key": "production",
            "label": "Production",
            "value": r["efficiency_pct"],
            "unit": "% efficiency",
            "score": sc.get("production"),
            "weight": weights["production"],
            "contribution": ct.get("production"),
            "source": f"{i['accepted']} accepted pieces × {smv} = {i['earned_min']:g} standard minutes over "
            f"{i['attended_min']:g} attended minutes ({i['downtime_min']:g} min machine downtime excluded). "
            f"Score is the efficiency percentile.{rank_txt}",
        },
        {
            "key": "quality",
            "label": "Quality",
            "value": r["first_pass_pct"],
            "unit": "% first pass",
            "score": sc.get("quality"),
            "weight": weights["quality"],
            "contribution": ct.get("quality"),
            "source": f"{i['accepted']} of {i['accepted'] + i['rework'] + i['rejected']} inspected pieces passed first time "
            f"({i['rework']} rework, {i['rejected']} rejected).",
        },
        {
            "key": "time",
            "label": "Time",
            "value": r["productive_pct"],
            "unit": "% productive",
            "score": sc.get("time"),
            "weight": weights["time"],
            "contribution": ct.get("time"),
            "source": f"{st.get('working', 0.0):g} working minutes of {round(time_den, 1):g} minutes at the station "
            f"(idle {st.get('idle', 0.0):g}, away {st.get('away', 0.0):g}, phone use {st.get('phone_use', 0.0):g}, "
            f"uncertain {st.get('uncertain', 0.0):g}). Rejected detections not counted: {rejected_txt}.",
        },
    ]


@router.get("/performance/workers/{worker_id}")
async def explain(
    worker_id: int,
    days: int | None = Query(default=None, ge=1, le=90),
    group: str | None = Query(default=None, max_length=32),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(*VIEWERS)),
):
    out = await compute(db, user, days, group, None)
    r = next((x for x in out["rows"] if x["worker"]["id"] == worker_id), None)
    if r is None:
        raise not_found("Worker performance")
    i = r["_inputs"]
    return ok(
        {
            **_public(r),
            "period": out["period"],
            "policy_version_id": out["policy_version_id"],
            "bonus_enabled": False,
            "components": _explain(r, out["policy"]["weights"]),
            "excluded": {
                "downtime_min": i["downtime_min"],
                "rejected_min": i["rejected_min"],
                "break_min": i["state_min"].get("break", 0.0),
                "scheduled_min": i["scheduled_min"],
            },
        }
    )


__all__ = ["compute", "router"]
