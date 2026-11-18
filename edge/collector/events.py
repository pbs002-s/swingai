"""Event shape sent to POST /api/v1/ingest/events (docs/API.md §9).

The state table mirrors apps/api/app/models/events.py EVENT_STATES. Keep both in sync: an event the
API would reject is better caught here, before it sits in the outbox.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

EVENT_STATES: dict[str, frozenset[str]] = {
    "worker_state": frozenset({"working", "idle", "phone_use", "away", "break", "uncertain"}),
    "machine_state": frozenset({"running", "stopped"}),
    "production_count": frozenset({"count"}),
    "needle_event": frozenset({"suspected_break", "needle_break", "thread_break", "jam", "other"}),
    "quality_event": frozenset({"possible_skipped_stitch", "possible_puckering", "other_defect", "no_defect"}),
    "rfid_tap": frozenset({"tap"}),
}
STATION_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
MAX_METADATA_KEYS = 32


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetime; use an aware UTC datetime")
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_event(
    event_type: str,
    state: str,
    station_code: str,
    start_time: datetime | None = None,
    *,
    confidence: float | None = None,
    model_version: str | None = None,
    metadata: dict[str, Any] | None = None,
    source_device_code: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_uuid": str(uuid.uuid4()),
        "event_type": event_type,
        "state": state,
        "station_code": station_code,
        "start_time": iso_utc(start_time or datetime.now(UTC)),
        "metadata": metadata or {},
    }
    if confidence is not None:
        event["confidence"] = round(float(confidence), 3)
    if model_version:
        event["model_version"] = model_version
    if source_device_code:
        event["source_device_code"] = source_device_code
    error = validate_event(event)
    if error:
        raise ValueError(error)
    return event


def validate_event(event: dict[str, Any]) -> str | None:
    """Return why the API would reject this event, or None if it looks valid."""
    try:
        uuid.UUID(str(event["event_uuid"]))
    except (KeyError, ValueError):
        return "event_uuid missing or not a UUID"
    states = EVENT_STATES.get(event.get("event_type", ""))
    if states is None:
        return f"unsupported event_type {event.get('event_type')!r}"
    if event.get("state") not in states:
        return f"state {event.get('state')!r} not valid for {event['event_type']}"
    if not STATION_CODE.match(str(event.get("station_code", ""))):
        return "station_code missing or malformed"
    try:
        start = datetime.fromisoformat(str(event["start_time"]))
    except (KeyError, ValueError):
        return "start_time missing or not ISO 8601"
    if start.tzinfo is None:
        return "start_time has no time zone"
    conf = event.get("confidence")
    if conf is not None and not 0 <= conf <= 1:
        return "confidence must be within 0..1"
    meta = event.get("metadata", {})
    if not isinstance(meta, dict) or len(meta) > MAX_METADATA_KEYS:
        return "metadata must be an object with at most 32 keys"
    return None
