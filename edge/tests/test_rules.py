from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vision.rules import (
    AWAY,
    BREAK,
    IDLE,
    PHONE_USE,
    STATES,
    UNCERTAIN,
    WORKING,
    Observation,
    RulesConfig,
    StationRules,
)

T0 = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
FPS = 5

WORK = {"person_in_zone": True, "hands_in_work_zone": True, "machine_running": True}
PAUSE = {"person_in_zone": True, "hands_in_work_zone": False, "machine_running": False}
GONE = {"person_in_zone": False}
PHONE = {**PAUSE, "phone_in_hand": True, "phone_confidence": 0.9, "head_down_to_phone": True}


def run(rules: StationRules, start_s: float, seconds: float, **fields) -> list:
    """Feed `seconds` of frames at FPS starting at start_s; return transitions."""
    out = []
    for i in range(round(seconds * FPS)):
        tr = rules.update(Observation(T0 + timedelta(seconds=start_s + i / FPS), **fields))
        if tr:
            out.append(tr)
    return out


def working(rules: StationRules) -> float:
    trs = run(rules, 0, 10, **WORK)
    assert [t.state for t in trs] == [WORKING]
    return 10


def test_working_needs_hold_then_starts_at_first_frame():
    rules = StationRules()
    assert run(rules, 0, 2.8, **WORK) == []  # < hold_s
    trs = run(rules, 2.8, 1, **WORK)
    assert [t.state for t in trs] == [WORKING]
    assert trs[0].start_time == T0  # back-dated to when the state began


def test_machine_running_alone_is_working():
    trs = run(StationRules(), 0, 5, person_in_zone=True, hands_in_work_zone=False, machine_running=True)
    assert [t.state for t in trs] == [WORKING]


def test_single_bad_frame_does_not_flip_state():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 0.2, person_in_zone=None) == []
    assert run(rules, t + 0.2, 5, **WORK) == []
    assert rules.state == WORKING


def test_away_after_60_seconds_dated_from_leaving():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 59.8, **GONE) == []
    trs = run(rules, t + 59.8, 1, **GONE)
    assert [x.state for x in trs] == [AWAY]
    assert trs[0].start_time == T0 + timedelta(seconds=t)


def test_short_absence_keeps_working():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 45, **GONE) == []
    assert run(rules, t + 45, 10, **WORK) == []
    assert rules.state == WORKING


def test_return_from_away_to_working():
    rules = StationRules()
    t = working(rules)
    run(rules, t, 70, **GONE)
    trs = run(rules, t + 70, 5, **WORK)
    assert [x.state for x in trs] == [WORKING]


def test_phone_use_after_20_seconds_with_work_stopped():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 19.8, **PHONE) == []
    trs = run(rules, t + 19.8, 1, **PHONE)
    assert [x.state for x in trs] == [PHONE_USE]
    assert trs[0].needs_review is True
    assert trs[0].confidence == pytest.approx(0.9)
    assert trs[0].start_time == T0 + timedelta(seconds=t)


def test_phone_resting_while_working_stays_working():
    rules = StationRules()
    t = working(rules)
    phone_on_table = {**WORK, "phone_in_hand": True, "phone_confidence": 0.95, "head_down_to_phone": True}
    assert run(rules, t, 120, **phone_on_table) == []
    assert rules.state == WORKING


def test_phone_with_hands_working_but_machine_stopped_counts():
    rules = StationRules()
    t = working(rules)
    fields = {**PHONE, "hands_in_work_zone": True, "machine_running": False}
    assert [x.state for x in run(rules, t, 25, **fields)] == [PHONE_USE]


def test_low_confidence_phone_is_not_phone_use():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 60, **{**PHONE, "phone_confidence": 0.6}) == []
    assert rules.state == WORKING  # a pause shorter than idle_after_s


def test_phone_without_head_down_is_not_phone_use_by_default():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 60, **{**PHONE, "head_down_to_phone": False}) == []
    relaxed = StationRules(RulesConfig(phone_requires_head_down=False))
    working(relaxed)
    assert [x.state for x in run(relaxed, t, 25, **{**PHONE, "head_down_to_phone": False})] == [PHONE_USE]


def test_phone_interrupted_restarts_the_20_second_window():
    rules = StationRules()
    t = working(rules)
    run(rules, t, 15, **PHONE)
    run(rules, t + 15, 1, **WORK)
    assert run(rules, t + 16, 15, **PHONE) == []
    assert rules.state == WORKING


def test_idle_after_5_minutes_dated_from_pause_start():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 299.8, **PAUSE) == []
    trs = run(rules, t + 299.8, 1, **PAUSE)
    assert [x.state for x in trs] == [IDLE]
    assert trs[0].start_time == T0 + timedelta(seconds=t)


def test_short_pause_stays_working():
    rules = StationRules()
    t = working(rules)
    assert run(rules, t, 120, **PAUSE) == []
    assert run(rules, t + 120, 5, **WORK) == []


def test_break_takes_precedence_immediately_over_everything():
    rules = StationRules()
    t = working(rules)
    trs = run(rules, t, 1, **PHONE, scheduled_break=True)
    assert [x.state for x in trs] == [BREAK]
    assert trs[0].start_time == T0 + timedelta(seconds=t)
    assert run(rules, t + 1, 120, **GONE, scheduled_break=True) == []
    assert [x.state for x in run(rules, t + 121, 5, **WORK)] == [WORKING]


def test_no_camera_view_is_uncertain_not_a_guess():
    rules = StationRules()
    t = working(rules)
    trs = run(rules, t, 5, person_in_zone=None)
    assert [x.state for x in trs] == [UNCERTAIN]


def test_present_but_no_signals_is_uncertain():
    trs = run(StationRules(), 0, 5, person_in_zone=True)
    assert [x.state for x in trs] == [UNCERTAIN]


def test_after_phone_put_down_without_work_becomes_uncertain():
    rules = StationRules()
    t = working(rules)
    run(rules, t, 25, **PHONE)
    trs = run(rules, t + 25, 5, **PAUSE)
    assert [x.state for x in trs] == [UNCERTAIN]


def test_out_of_order_frames_are_ignored_and_time_never_goes_back():
    rules = StationRules()
    t = working(rules)
    assert rules.update(Observation(T0, **GONE)) is None
    run(rules, t, 70, **GONE)
    trs = run(rules, t + 70, 400, **PAUSE)
    assert [x.state for x in trs] == [UNCERTAIN, IDLE]
    assert trs[0].start_time <= trs[1].start_time


def test_thresholds_come_from_config():
    cfg = RulesConfig.from_dict({"away_after_s": 10, "hold_s": 1, "unknown_key": 5})
    rules = StationRules(cfg)
    run(rules, 0, 2, **WORK)
    assert [x.state for x in run(rules, 2, 11, **GONE)] == [AWAY]


def test_states_match_api_and_never_name_a_place():
    assert set(STATES) == {"working", "idle", "phone_use", "away", "break", "uncertain"}
    forbidden = "wash" + "room"
    root = Path(__file__).resolve().parents[1]
    sources = [
        p
        for p in root.rglob("*")
        if p.suffix in {".py", ".ino", ".h", ".json"} and ".venv" not in p.parts and p.name != Path(__file__).name
    ]
    assert sources
    for p in sources:
        assert forbidden not in p.read_text(encoding="utf-8", errors="ignore").lower(), p
