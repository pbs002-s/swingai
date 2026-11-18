"""Per-station worker-state machine (docs/VISION_AND_SENSING_PLAN.md §3.2). Pure Python, no ML imports.

Precedence, evaluated every frame (~5 fps):

    scheduled break                                   -> break
    camera has no view of the zone (person unknown)   -> uncertain
    person absent >= away_after_s                     -> away  (shorter absences keep the current state)
    phone in hand (+ head down) with confidence >= min
        AND work stopped (hands out of zone OR machine stopped)
        for >= phone_min_s                            -> phone_use (always goes to supervisor review)
    hands in work zone OR machine running             -> working
    present, hands idle, machine not running
        for >= idle_after_s                           -> idle  (a shorter pause keeps `working`)
    otherwise                                         -> uncertain

The system only ever knows a worker is *away* from the station; it never guesses where they went.
Working / uncertain must hold for `hold_s` before the state changes (hysteresis), so one bad frame
does not flip it. Duration-based states already include their own hold. Thresholds are policy data.
"""

from dataclasses import dataclass, field
from datetime import datetime

WORKING, IDLE, PHONE_USE, AWAY, BREAK, UNCERTAIN = "working", "idle", "phone_use", "away", "break", "uncertain"
STATES = (WORKING, IDLE, PHONE_USE, AWAY, BREAK, UNCERTAIN)
_TIMED = {AWAY, PHONE_USE, IDLE, BREAK}  # these carry their own duration; no extra hold


@dataclass(frozen=True)
class RulesConfig:
    away_after_s: float = 60.0
    phone_min_s: float = 20.0
    phone_min_confidence: float = 0.75
    phone_requires_head_down: bool = True
    idle_after_s: float = 300.0
    hold_s: float = 3.0

    @classmethod
    def from_dict(cls, data: dict | None) -> "RulesConfig":
        known = {k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass(frozen=True)
class Observation:
    """One frame's evidence for one station. None means "could not tell" (no camera view, no sensor)."""

    ts: datetime
    person_in_zone: bool | None
    hands_in_work_zone: bool | None = None
    phone_in_hand: bool = False
    phone_confidence: float = 0.0
    head_down_to_phone: bool = False
    machine_running: bool | None = None
    scheduled_break: bool = False


@dataclass(frozen=True)
class Transition:
    state: str
    start_time: datetime
    confidence: float | None = None
    needs_review: bool = False
    metadata: dict = field(default_factory=dict)


def _secs(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds()


class StationRules:
    def __init__(self, config: RulesConfig | None = None):
        self.cfg = config or RulesConfig()
        self.state: str | None = None
        self.state_since: datetime | None = None
        self._last_ts: datetime | None = None
        self._pending: str | None = None
        self._pending_since: datetime | None = None
        self._absent_since: datetime | None = None
        self._phone_since: datetime | None = None
        self._phone_confs: list[float] = []
        self._idle_since: datetime | None = None

    def update(self, obs: Observation) -> Transition | None:
        """Feed one frame; return a Transition when the station's state changes."""
        if self._last_ts is not None and obs.ts <= self._last_ts:
            return None  # out-of-order or repeated frame
        self._last_ts = obs.ts
        self._track(obs)
        cand, since, conf = self._candidate(obs)
        if cand is None or cand == self.state:
            self._pending = None
            return None
        if cand not in _TIMED:
            if self._pending != cand:
                self._pending, self._pending_since = cand, obs.ts
            if _secs(obs.ts, self._pending_since) < self.cfg.hold_s:
                return None
            since = self._pending_since
        if self.state_since is not None and since < self.state_since:
            since = self.state_since  # transitions never go back in time
        self.state, self.state_since, self._pending = cand, since, None
        meta = {"rule": cand}
        if cand == PHONE_USE:
            meta["phone_frames"] = len(self._phone_confs)
        return Transition(cand, since, conf, needs_review=cand == PHONE_USE, metadata=meta)

    def _track(self, obs: Observation) -> None:
        present = obs.person_in_zone is True
        absent = obs.person_in_zone is False
        self._absent_since = (self._absent_since or obs.ts) if absent else None

        work_stopped = obs.hands_in_work_zone is False or obs.machine_running is False
        phone = (
            present
            and obs.phone_in_hand
            and obs.phone_confidence >= self.cfg.phone_min_confidence
            and (obs.head_down_to_phone or not self.cfg.phone_requires_head_down)
            and work_stopped
        )
        if phone:
            self._phone_since = self._phone_since or obs.ts
            self._phone_confs.append(obs.phone_confidence)
        else:
            self._phone_since, self._phone_confs = None, []

        idle = present and obs.hands_in_work_zone is False and obs.machine_running is not True
        self._idle_since = (self._idle_since or obs.ts) if idle else None

    def _candidate(self, obs: Observation) -> tuple[str | None, datetime, float | None]:
        cfg = self.cfg
        if obs.scheduled_break:
            return BREAK, obs.ts, None
        if obs.person_in_zone is None:
            return UNCERTAIN, obs.ts, None
        if obs.person_in_zone is False:
            if _secs(obs.ts, self._absent_since) >= cfg.away_after_s:
                return AWAY, self._absent_since, None
            return None, obs.ts, None  # short absence: keep the current state
        if self._phone_since is not None and _secs(obs.ts, self._phone_since) >= cfg.phone_min_s:
            conf = sum(self._phone_confs) / len(self._phone_confs)
            return PHONE_USE, self._phone_since, round(conf, 3)
        if obs.hands_in_work_zone is True or obs.machine_running is True:
            return WORKING, obs.ts, None
        if self._idle_since is not None:
            if _secs(obs.ts, self._idle_since) >= cfg.idle_after_s:
                return IDLE, self._idle_since, None
            if self.state == WORKING:
                return None, obs.ts, None  # a short pause is still work
        return UNCERTAIN, obs.ts, None
