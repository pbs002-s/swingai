"""Edge collector entry point: `uv run python -m collector.main`.

MQTT sensors -> outbox; vision process writes to the same outbox; sender pushes to the central API.
"""

import asyncio
import contextlib
import json
import logging
import signal
import sys
from datetime import UTC, datetime

import httpx

from collector.config import Settings
from collector.control import Control, every
from collector.mqtt_bridge import Converter, MqttBridge
from collector.outbox import Outbox
from collector.sender import Sender

log = logging.getLogger("collector")
HEARTBEAT_S = 30
CONFIG_PULL_S = 300


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def run(settings: Settings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows: Ctrl+C arrives as KeyboardInterrupt
            loop.add_signal_handler(sig, stop.set)

    outbox = Outbox(settings.outbox_path)
    converter = Converter(settings.device_code)
    bridge = MqttBridge(
        outbox, converter, settings.mqtt_host, settings.mqtt_port, settings.mqtt_username, settings.mqtt_password
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        sender = Sender(client, outbox, settings.api_url, settings.device_token)
        control = Control(
            client, settings.api_url, settings.device_token, outbox, converter, settings.config_cache_path
        )
        bridge.start()
        log.info(
            "collector started: api=%s outbox=%s pending=%s", settings.api_url, settings.outbox_path, outbox.counts()
        )
        tasks = [
            asyncio.create_task(sender.run(stop)),
            asyncio.create_task(every(HEARTBEAT_S, stop, control.heartbeat)),
            asyncio.create_task(every(CONFIG_PULL_S, stop, control.pull_config)),
        ]
        try:
            await stop.wait()
        finally:
            stop.set()
            bridge.stop()
            await asyncio.gather(*tasks, return_exceptions=True)
            log.info("collector stopped: outbox=%s", outbox.counts())
            outbox.close()


def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(settings))


if __name__ == "__main__":
    main()
