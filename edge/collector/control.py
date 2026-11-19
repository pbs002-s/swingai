"""Heartbeat (every 30 s) and config pull (GET /api/v1/edge/config every 5 min).

The config endpoint may not exist yet on the central API; a 404 is logged once and the last cached
config (a JSON file next to the outbox) stays in use.
"""

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from collector.live import register_streams
from collector.mqtt_bridge import Converter
from collector.outbox import Outbox

log = logging.getLogger(__name__)
HEARTBEAT_PATH = "/api/v1/ingest/heartbeat"
CONFIG_PATH = "/api/v1/edge/config"


async def every(seconds: float, stop: asyncio.Event, fn: Callable[[], Awaitable[None]]) -> None:
    while not stop.is_set():
        try:
            await fn()
        except httpx.HTTPError as exc:
            log.warning("%s failed: %s", fn.__name__, exc.__class__.__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            pass


class Control:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        token: str,
        outbox: Outbox,
        converter: Converter,
        cache_path: str | Path,
        go2rtc_url: str = "",
        go2rtc_auth: tuple[str, str] | None = None,
    ):
        self.client, self.outbox, self.converter = client, outbox, converter
        self.base = api_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.cache_path = Path(cache_path)
        self.go2rtc_url = go2rtc_url
        self.go2rtc_auth = go2rtc_auth
        self.config: dict[str, Any] | None = self._load_cache()
        self._config_missing_logged = False

    def _load_cache(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except ValueError:
            log.warning("ignored unreadable config cache %s", self.cache_path)
            return None

    async def heartbeat(self) -> None:
        body = {"outbox": self.outbox.counts(), "devices": self.converter.devices}
        resp = await self.client.post(self.base + HEARTBEAT_PATH, json=body, headers=self.headers)
        if not resp.is_success:
            log.warning("heartbeat refused: HTTP %d", resp.status_code)

    async def pull_config(self) -> None:
        resp = await self.client.get(self.base + CONFIG_PATH, headers=self.headers)
        if resp.status_code == 404:
            if not self._config_missing_logged:
                log.info("edge config endpoint not available yet (404); using cached config")
                self._config_missing_logged = True
            return
        if not resp.is_success:
            log.warning("config pull refused: HTTP %d", resp.status_code)
            return
        try:
            body = resp.json()
            config = body.get("data", body)
        except ValueError:
            log.warning("config pull returned non-JSON")
            return
        if config != self.config:
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
            os.replace(tmp, self.cache_path)  # atomic, so the vision process never reads half a file
            self.config = config
            log.info("edge config updated")
        if self.go2rtc_url and self.config:
            await register_streams(self.client, self.go2rtc_url, self.config.get("cameras", []), self.go2rtc_auth)
