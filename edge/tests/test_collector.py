import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from collector.control import Control
from collector.events import make_event, validate_event
from collector.mqtt_bridge import Converter, Malformed
from collector.outbox import Outbox
from collector.sender import RetryLater, Sender, backoff_delay

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


class Clock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def ev(state: str = "running", station: str = "L1-S01") -> dict:
    return make_event("machine_state", state, station, NOW)


# ---- events / outbox ----------------------------------------------------------------------------


def test_make_event_validates_against_api_states():
    e = make_event("worker_state", "phone_use", "L1-S07", NOW, confidence=0.871234)
    assert e["start_time"] == "2026-11-17T03:00:00.000Z" and e["confidence"] == 0.871
    with pytest.raises(ValueError):
        make_event("worker_state", "toilet", "L1-S07", NOW)
    with pytest.raises(ValueError):
        make_event("machine_state", "running", "bad code with spaces", NOW)
    assert validate_event({**e, "start_time": "2026-11-17T03:00:00"}) == "start_time has no time zone"


def test_outbox_add_batch_mark_and_dedupe():
    box = Outbox(":memory:")
    events = [ev() for _ in range(5)]
    assert all(box.add(e) for e in events)
    assert box.add(events[0]) is False  # same UUID twice
    assert [e["event_uuid"] for e in box.next_batch(3)] == [e["event_uuid"] for e in events[:3]]
    box.mark_sent([events[0]["event_uuid"], events[1]["event_uuid"]])
    box.park({events[2]["event_uuid"]: "UNKNOWN_STATION"})
    assert [e["event_uuid"] for e in box.next_batch()] == [e["event_uuid"] for e in events[3:]]
    assert box.counts() == {"pending": 2, "rejected": 1}
    assert box.rejected() == [(events[2]["event_uuid"], "UNKNOWN_STATION")]


def test_outbox_rejects_invalid_event():
    with pytest.raises(ValueError):
        Outbox(":memory:").add({"event_uuid": "x"})


def test_outbox_retention_drops_only_old_rows(tmp_path, caplog):
    clock = Clock()
    box = Outbox(tmp_path / "o.sqlite3", clock=clock)
    old = ev()
    box.add(old)
    clock.t += 72 * 3600 - 10
    fresh = ev()
    box.add(fresh)
    clock.t += 20
    assert box.prune() == 1
    assert "dropped 1 events" in caplog.text
    assert [e["event_uuid"] for e in box.next_batch()] == [fresh["event_uuid"]]


def test_outbox_survives_reopen(tmp_path):
    path = tmp_path / "o.sqlite3"
    box = Outbox(path)
    e = ev()
    box.add(e)
    box.close()
    assert Outbox(path).next_batch()[0] == e


# ---- sender -------------------------------------------------------------------------------------


def make_sender(handler, box: Outbox) -> Sender:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Sender(client, box, "http://api.test/", "tok-123")


def envelope(results: list[dict]) -> dict:
    counts = {s: sum(r["status"] == s for r in results) for s in ("accepted", "duplicate", "rejected")}
    return {"success": True, "data": {**counts, "results": results}, "error": None, "meta": {}}


def test_sender_partial_results_mark_sent_and_park_rejected():
    box = Outbox(":memory:")
    a, b, c = ev(), ev(), ev("stopped", "NOPE-1")
    for e in (a, b, c):
        box.add(e)
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"], seen["url"] = req.headers["authorization"], str(req.url)
        seen["n"] = len(json.loads(req.content)["events"])
        return httpx.Response(
            200,
            json=envelope(
                [
                    {"event_uuid": a["event_uuid"], "status": "accepted", "event_id": 1, "error": None},
                    {"event_uuid": b["event_uuid"], "status": "duplicate", "event_id": None, "error": None},
                    {"event_uuid": c["event_uuid"], "status": "rejected", "event_id": None, "error": "UNKNOWN_STATION"},
                ]
            ),
        )

    assert asyncio.run(make_sender(handler, box).send_once()) == 3
    assert seen == {"auth": "Bearer tok-123", "url": "http://api.test/api/v1/ingest/events", "n": 3}
    assert box.counts() == {"pending": 0, "rejected": 1}
    assert box.rejected() == [(c["event_uuid"], "UNKNOWN_STATION")]


@pytest.mark.parametrize("status", [500, 502, 503, 401, 404, 429])
def test_sender_retryable_status_keeps_rows(status):
    box = Outbox(":memory:")
    box.add(ev())
    headers = {"retry-after": "7"} if status == 429 else {}
    sender = make_sender(lambda r: httpx.Response(status, json={"error": {"code": "X"}}, headers=headers), box)
    with pytest.raises(RetryLater) as info:
        asyncio.run(sender.send_once())
    assert box.counts()["pending"] == 1
    if status == 429:
        assert info.value.retry_after == 7


def test_sender_network_error_is_retryable():
    box = Outbox(":memory:")
    box.add(ev())

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    with pytest.raises(RetryLater):
        asyncio.run(make_sender(handler, box).send_once())
    assert box.counts()["pending"] == 1


def test_sender_validation_error_parks_only_named_rows():
    box = Outbox(":memory:")
    good, bad = ev(), ev()
    box.add(good)
    box.add(bad)
    body = {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "details": {"fields": [{"loc": ["body", "events", 1, "state"], "msg": "bad"}]},
        },
    }
    assert asyncio.run(make_sender(lambda r: httpx.Response(400, json=body), box).send_once()) == 1
    assert box.rejected() == [(bad["event_uuid"], "VALIDATION_ERROR")]
    assert [e["event_uuid"] for e in box.next_batch()] == [good["event_uuid"]]


def test_sender_other_4xx_parks_whole_batch_so_it_is_not_retried_forever():
    box = Outbox(":memory:")
    box.add(ev())
    box.add(ev())
    asyncio.run(make_sender(lambda r: httpx.Response(413, text="too big"), box).send_once())
    assert box.counts() == {"pending": 0, "rejected": 2}
    assert {code for _, code in box.rejected()} == {"HTTP_413"}


def test_run_retries_5xx_then_delivers():
    box = Outbox(":memory:")
    e = ev()
    box.add(e)
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=envelope([{"event_uuid": e["event_uuid"], "status": "accepted"}]))

    async def go():
        sender = make_sender(handler, box)
        sender.backoff_base_s, sender.idle_wait_s = 0.001, 0.001
        stop = asyncio.Event()
        task = asyncio.create_task(sender.run(stop))
        for _ in range(200):
            await asyncio.sleep(0.005)
            if box.counts()["pending"] == 0:
                break
        stop.set()
        await task

    asyncio.run(go())
    assert len(calls) == 3 and box.counts()["pending"] == 0


def test_backoff_grows_with_jitter_and_caps():
    assert backoff_delay(0, rng=lambda: 0.0) == 0.5
    assert backoff_delay(3, rng=lambda: 1.0) == 8.0
    assert backoff_delay(50, cap=300, rng=lambda: 0.0) == 150.0
    assert 4.0 <= backoff_delay(3) <= 8.0


# ---- control ------------------------------------------------------------------------------------


def test_config_pull_tolerates_404_and_caches_on_success(tmp_path):
    box, cache = Outbox(":memory:"), tmp_path / "edge_config.json"
    responses = [httpx.Response(404), httpx.Response(200, json={"success": True, "data": {"stations": ["L1-S01"]}})]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: responses.pop(0)))
    control = Control(client, "http://api.test", "tok", box, Converter(), cache)
    asyncio.run(control.pull_config())
    assert control.config is None and not cache.exists()
    asyncio.run(control.pull_config())
    assert json.loads(cache.read_text()) == {"stations": ["L1-S01"]}
    assert Control(client, "http://api.test", "tok", box, Converter(), cache).config == {"stations": ["L1-S01"]}


# ---- mqtt conversion ----------------------------------------------------------------------------


def msg(d) -> bytes:
    return json.dumps(d).encode()


def test_machine_state_emits_only_on_change():
    conv = Converter("EDGE-1")
    first = conv.convert("factory/L1-S01/machine/state", msg({"running": True, "current_a": 1.84}), NOW)
    assert (first["event_type"], first["state"], first["station_code"]) == ("machine_state", "running", "L1-S01")
    assert first["metadata"] == {"current_a": 1.84} and first["source_device_code"] == "EDGE-1"
    assert conv.convert("factory/L1-S01/machine/state", msg({"running": True}), NOW) is None
    assert conv.convert("factory/L1-S01/machine/state", msg({"running": False}), NOW)["state"] == "stopped"
    assert conv.convert("factory/L1-S02/machine/state", msg({"running": False}), NOW)["state"] == "stopped"


def test_device_timestamp_used_only_when_sane():
    conv = Converter()
    ok_ts = (NOW - timedelta(seconds=2)).isoformat()
    e = conv.convert("factory/L1-S01/machine/state", msg({"running": True, "ts": ok_ts}), NOW)
    assert e["start_time"] == "2026-11-17T02:59:58.000Z"
    e = conv.convert("factory/L1-S01/machine/state", msg({"running": False, "ts": "1970-01-01T00:00:10Z"}), NOW)
    assert e["start_time"] == "2026-11-17T03:00:00.000Z"


def test_rfid_tap_and_needle_alarm():
    conv = Converter()
    tap = conv.convert("factory/L1-S01/rfid/tap", msg({"card_id": "04A1B2C3"}), NOW)
    assert (tap["event_type"], tap["state"], tap["metadata"]) == ("rfid_tap", "tap", {"card_id": "04A1B2C3"})
    for t in ("suspected_break", "break"):
        alarm = conv.convert("factory/L1-S01/needle/alarm", msg({"type": t}), NOW)
        assert (alarm["event_type"], alarm["state"]) == ("needle_event", "suspected_break")


def test_heartbeat_is_remembered_not_sent_as_event():
    conv = Converter()
    assert conv.convert("devices/SENS-L1-S01/heartbeat", msg({"fw": "1.2.0", "rssi": -61, "x": [1]}), NOW) is None
    assert conv.devices["SENS-L1-S01"] == {"fw": "1.2.0", "rssi": -61, "last_seen": NOW.isoformat()}


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        ("factory/L1-S01/machine/state", b"not json"),
        ("factory/L1-S01/machine/state", msg([1, 2])),
        ("factory/L1-S01/machine/state", msg({"running": "yes"})),
        ("factory/L1-S01/machine/state", msg({"running": True, "current_a": "lots"})),
        ("factory/L1-S01/rfid/tap", msg({"card_id": ""})),
        ("factory/L1-S01/rfid/tap", msg({"card_id": "x" * 100})),
        ("factory/L1-S01/needle/alarm", msg({"type": "fire"})),
        ("factory/has space/machine/state", msg({"running": True})),
        ("factory/L1-S01/other/thing", msg({})),
        ("factory/L1-S01/machine/state", b"{" + b" " * 5000 + b"}"),
    ],
)
def test_malformed_messages_raise(topic, payload):
    with pytest.raises(Malformed):
        Converter().convert(topic, payload, NOW)
