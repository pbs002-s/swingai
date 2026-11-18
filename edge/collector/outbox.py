"""SQLite outbox: every event is stored here before it is sent, so nothing is lost while offline.

Rows are pending until the API accepts them (or says duplicate), then deleted. Rows the API rejects
are parked with the error code and never retried. The collector and the vision process may share
one file: WAL mode lets several processes write.
"""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from collector.events import validate_event

log = logging.getLogger(__name__)
RETENTION_S = 72 * 3600

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    uuid TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | rejected
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_status_created ON outbox (status, created_at);
"""


class Outbox:
    def __init__(self, path: str | Path, retention_s: float = RETENTION_S, clock: Any = time.time):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, timeout=10, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()  # MQTT callbacks run on paho's thread
        self.retention_s = retention_s
        self._clock = clock

    def add(self, event: dict[str, Any]) -> bool:
        """Store an event. False if its UUID is already in the outbox. Raises ValueError if invalid."""
        error = validate_event(event)
        if error:
            raise ValueError(error)
        with self._lock:
            cur = self._db.execute(
                "INSERT OR IGNORE INTO outbox (uuid, created_at, body) VALUES (?, ?, ?)",
                (event["event_uuid"], self._clock(), json.dumps(event, separators=(",", ":"))),
            )
        return cur.rowcount == 1

    def next_batch(self, n: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT body FROM outbox WHERE status = 'pending' ORDER BY created_at LIMIT ?", (n,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def mark_sent(self, uuids: list[str]) -> None:
        with self._lock:
            self._db.executemany("DELETE FROM outbox WHERE uuid = ?", [(u,) for u in uuids])

    def park(self, errors: dict[str, str]) -> None:
        """Set rejected rows aside with their error code, so they are kept for inspection but not resent."""
        with self._lock:
            self._db.executemany(
                "UPDATE outbox SET status = 'rejected', error = ? WHERE uuid = ?", [(e, u) for u, e in errors.items()]
            )

    def prune(self) -> int:
        """Drop rows older than the retention window (pending or rejected); return how many."""
        cutoff = self._clock() - self.retention_s
        with self._lock:
            dropped = self._db.execute("DELETE FROM outbox WHERE created_at < ?", (cutoff,)).rowcount
        if dropped:
            log.warning("outbox retention dropped %d events older than %.0f h", dropped, self.retention_s / 3600)
        return dropped

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._db.execute("SELECT status, COUNT(*) FROM outbox GROUP BY status").fetchall()
        return {"pending": 0, "rejected": 0, **dict(rows)}

    def rejected(self) -> list[tuple[str, str]]:
        with self._lock:
            return self._db.execute("SELECT uuid, error FROM outbox WHERE status = 'rejected'").fetchall()

    def close(self) -> None:
        with self._lock:
            self._db.close()
