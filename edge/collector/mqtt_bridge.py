"""MQTT (sensors) -> API events. Topics from docs/TRD.md §4.2.

    factory/{station}/machine/state   {"running": true, "current_a": 1.84, "ts": "..."}  -> machine_state (on change)
    factory/{station}/rfid/tap        {"card_id": "04A1B2", "ts": "..."}                 -> rfid_tap
    factory/{station}/needle/alarm    {"type": "suspected_break", "ts": "..."}           -> needle_event suspected_break
    devices/{device}/heartbeat        {"fw": "1.2.0", "rssi": -61}                       -> remembered for the heartbeat

A sensor alarm is never a confirmed break: every needle alarm becomes `suspected_break` for review.
"""

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from collector.events import STATION_CODE, make_event
from collector.outbox import Outbox

log = logging.getLogger(__name__)
TOPICS = ["factory/+/machine/state", "factory/+/rfid/tap", "factory/+/needle/alarm", "devices/+/heartbeat"]
MAX_PAYLOAD = 4096
MAX_SKEW = timedelta(minutes=5)  # sensor clocks beyond this are ignored; the edge box (NTP) time is used
CARD_ID = re.compile(r"^[A-Za-z0-9:-]{1,64}$")
NEEDLE_ALARM_TYPES = {"suspected_break", "break"}


class Malformed(ValueError):
    pass


def _ts(payload: dict[str, Any], now: datetime) -> datetime:
    raw = payload.get("ts")
    if isinstance(raw, str):
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            return now
        if ts.tzinfo is not None and abs(ts - now) <= MAX_SKEW:
            return ts.astimezone(UTC)
    return now


class Converter:
    """Pure topic+payload -> event logic. Keeps the last machine state per station to emit only changes."""

    def __init__(self, source_device_code: str | None = None):
        self.machine_states: dict[str, bool] = {}
        self.devices: dict[str, dict[str, Any]] = {}
        self.source_device_code = source_device_code

    def convert(self, topic: str, raw: bytes, now: datetime | None = None) -> dict[str, Any] | None:
        """Return an event, or None when nothing should be sent. Raises Malformed for bad input."""
        now = now or datetime.now(UTC)
        if len(raw) > MAX_PAYLOAD:
            raise Malformed("payload too large")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise Malformed("payload is not JSON") from exc
        if not isinstance(payload, dict):
            raise Malformed("payload is not a JSON object")
        parts = topic.split("/")
        if len(parts) == 3 and parts[0] == "devices" and parts[2] == "heartbeat":
            return self._heartbeat(parts[1], payload, now)
        if len(parts) != 4 or parts[0] != "factory" or not STATION_CODE.match(parts[1]):
            raise Malformed(f"unexpected topic {topic!r}")
        station, kind = parts[1], f"{parts[2]}/{parts[3]}"
        if kind == "machine/state":
            return self._machine(station, payload, now)
        if kind == "rfid/tap":
            card = payload.get("card_id")
            if not isinstance(card, str) or not CARD_ID.match(card):
                raise Malformed("card_id missing or malformed")
            return self._event("rfid_tap", "tap", station, _ts(payload, now), {"card_id": card})
        if kind == "needle/alarm":
            if payload.get("type") not in NEEDLE_ALARM_TYPES:
                raise Malformed("needle alarm type missing or unknown")
            return self._event("needle_event", "suspected_break", station, _ts(payload, now), {"detector": "sensor"})
        raise Malformed(f"unexpected topic {topic!r}")

    def _machine(self, station: str, payload: dict[str, Any], now: datetime) -> dict[str, Any] | None:
        running = payload.get("running")
        if not isinstance(running, bool):
            raise Malformed("running must be true or false")
        meta: dict[str, Any] = {}
        current = payload.get("current_a")
        if current is not None:
            if isinstance(current, bool) or not isinstance(current, int | float) or not 0 <= current < 1000:
                raise Malformed("current_a must be a number in amps")
            meta["current_a"] = round(float(current), 3)
        if self.machine_states.get(station) == running:
            return None
        self.machine_states[station] = running
        return self._event("machine_state", "running" if running else "stopped", station, _ts(payload, now), meta)

    def _heartbeat(self, device: str, payload: dict[str, Any], now: datetime) -> None:
        if not STATION_CODE.match(device):
            raise Malformed("device code malformed")
        info = {k: payload[k] for k in ("fw", "rssi") if isinstance(payload.get(k), str | int | float)}
        self.devices[device] = {**info, "last_seen": now.isoformat()}
        return None

    def _event(self, event_type: str, state: str, station: str, at: datetime, meta: dict[str, Any]) -> dict[str, Any]:
        return make_event(event_type, state, station, at, metadata=meta, source_device_code=self.source_device_code)


class MqttBridge:
    """paho-mqtt client wired to a Converter and the outbox. paho reconnects by itself."""

    def __init__(
        self, outbox: Outbox, converter: Converter, host: str, port: int, username: str = "", password: str = ""
    ):
        import paho.mqtt.client as mqtt

        self.outbox, self.converter = outbox, converter
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="stitchsense-collector")
        if username:
            self.client.username_pw_set(username, password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.host, self.port = host, port

    def start(self) -> None:
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _props: Any = None) -> None:
        if reason_code.is_failure:
            log.error("mqtt connect failed: %s", reason_code)
            return
        client.subscribe([(t, 1) for t in TOPICS])
        log.info("mqtt connected to %s:%d, subscribed %s", self.host, self.port, TOPICS)

    def _on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        try:
            event = self.converter.convert(msg.topic, msg.payload)
        except (Malformed, ValueError) as exc:
            log.warning("ignored mqtt message on %s: %s", msg.topic, exc)
            return
        if event is not None:
            self.outbox.add(event)
