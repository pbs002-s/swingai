"""Push outbox batches to POST {SS_API_URL}/api/v1/ingest/events (docs/API.md §9).

- 2xx: per-row results. accepted / duplicate -> removed from the outbox; rejected -> parked with its code.
- 400 VALIDATION_ERROR: the rows named in details.fields are parked; the rest are resent next round.
- Network errors, 5xx, 401/403/404/408/429: nothing is lost; back off (exponential + jitter) and retry.
  Auth and 404 are retried because they are setup problems (token, URL) that an operator fixes.
- Any other 4xx: the whole batch is parked, so a poison batch is never retried forever.
"""

import asyncio
import logging
import random
from collections.abc import Callable
from typing import Any

import httpx

from collector.outbox import Outbox

log = logging.getLogger(__name__)
INGEST_PATH = "/api/v1/ingest/events"
RETRY_STATUSES = {401, 403, 404, 408, 429}
SENT_STATUSES = {"accepted", "duplicate"}


class RetryLater(Exception):
    def __init__(self, reason: str, retry_after: float | None = None):
        super().__init__(reason)
        self.retry_after = retry_after


def backoff_delay(
    attempt: int, base: float = 1.0, cap: float = 300.0, rng: Callable[[], float] = random.random
) -> float:
    """Exponential backoff with jitter: a random delay in [half, full] of min(cap, base * 2**attempt)."""
    full = min(cap, base * 2 ** min(attempt, 30))
    return full / 2 + rng() * full / 2


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers["retry-after"])
    except (KeyError, ValueError):
        return None


def _error_code(resp: httpx.Response) -> str:
    try:
        return str(resp.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP_{resp.status_code}"


def _invalid_rows(resp: httpx.Response, batch: list[dict[str, Any]]) -> set[int]:
    """Row indexes named by a VALIDATION_ERROR, from loc like ["body", "events", 3, "state"]."""
    try:
        fields = resp.json()["error"]["details"]["fields"]
    except (ValueError, KeyError, TypeError):
        return set()
    rows = set()
    for f in fields:
        loc = f.get("loc", []) if isinstance(f, dict) else []
        if len(loc) >= 3 and loc[1] == "events" and isinstance(loc[2], int) and 0 <= loc[2] < len(batch):
            rows.add(loc[2])
    return rows


class Sender:
    def __init__(
        self,
        client: httpx.AsyncClient,
        outbox: Outbox,
        api_url: str,
        token: str,
        batch_size: int = 500,
        idle_wait_s: float = 2.0,
        backoff_base_s: float = 1.0,
        backoff_cap_s: float = 300.0,
    ):
        self.client, self.outbox = client, outbox
        self.url = api_url.rstrip("/") + INGEST_PATH
        self.headers = {"Authorization": f"Bearer {token}"}
        self.batch_size = min(batch_size, 500)
        self.idle_wait_s, self.backoff_base_s, self.backoff_cap_s = idle_wait_s, backoff_base_s, backoff_cap_s

    async def send_once(self) -> int:
        """Send one batch. Returns how many rows left the pending queue. Raises RetryLater."""
        batch = self.outbox.next_batch(self.batch_size)
        if not batch:
            return 0
        try:
            resp = await self.client.post(self.url, json={"events": batch}, headers=self.headers)
        except httpx.TransportError as exc:
            raise RetryLater(f"network: {exc.__class__.__name__}") from exc
        if resp.status_code >= 500 or resp.status_code in RETRY_STATUSES:
            raise RetryLater(f"HTTP {resp.status_code} {_error_code(resp)}", _retry_after(resp))
        if resp.is_success:
            return self._apply_results(resp, batch)
        code = _error_code(resp)
        bad = _invalid_rows(resp, batch) if code == "VALIDATION_ERROR" else set()
        parked = [batch[i] for i in bad] or batch
        self.outbox.park({e["event_uuid"]: code for e in parked})
        log.error("ingest refused %d of %d events: HTTP %d %s", len(parked), len(batch), resp.status_code, code)
        return len(parked)

    def _apply_results(self, resp: httpx.Response, batch: list[dict[str, Any]]) -> int:
        try:
            data = resp.json()
            results = data.get("data", data)["results"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RetryLater("2xx without per-row results") from exc
        sent, rejected = [], {}
        for r in results:
            if r.get("status") in SENT_STATUSES:
                sent.append(r["event_uuid"])
            elif r.get("status") == "rejected":
                rejected[r["event_uuid"]] = r.get("error") or "REJECTED"
        self.outbox.mark_sent(sent)
        self.outbox.park(rejected)
        if rejected:
            log.warning("ingest rejected %d events: %s", len(rejected), sorted(set(rejected.values())))
        missing = len(batch) - len(sent) - len(rejected)
        if missing:
            log.warning("ingest response had no result for %d events; they stay pending", missing)
        return len(sent) + len(rejected)

    async def run(self, stop: asyncio.Event, prune_every_s: float = 600.0) -> None:
        attempt = 0
        loop = asyncio.get_running_loop()
        next_prune = 0.0
        while not stop.is_set():
            if loop.time() >= next_prune:
                self.outbox.prune()
                next_prune = loop.time() + prune_every_s
            try:
                moved = await self.send_once()
                attempt = 0
                wait = 0.0 if moved else self.idle_wait_s
            except RetryLater as exc:
                wait = exc.retry_after or backoff_delay(attempt, self.backoff_base_s, self.backoff_cap_s)
                attempt += 1
                log.warning("ingest send failed (%s); retry %d in %.1f s", exc, attempt, wait)
            if wait:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=wait)
                except TimeoutError:
                    pass
