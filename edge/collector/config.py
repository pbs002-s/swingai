"""Collector settings from environment variables (see edge/README.md)."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    api_url: str
    device_token: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    outbox_path: Path
    config_cache_path: Path
    device_code: str | None
    log_level: str
    go2rtc_url: str = ""

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        api_url = env.get("SS_API_URL", "http://localhost:8000")
        if urlparse(api_url).scheme not in ("http", "https"):
            raise ValueError("SS_API_URL must start with http:// or https://")
        token = env.get("SS_DEVICE_TOKEN", "")
        if not token:
            raise ValueError("SS_DEVICE_TOKEN is required (the edge box's device token)")
        outbox = Path(env.get("OUTBOX_PATH", "data/outbox.sqlite3"))
        return cls(
            api_url=api_url,
            device_token=token,
            mqtt_host=env.get("MQTT_HOST", "localhost"),
            mqtt_port=int(env.get("MQTT_PORT", "1883")),
            mqtt_username=env.get("MQTT_USERNAME", ""),
            mqtt_password=env.get("MQTT_PASSWORD", ""),
            outbox_path=outbox,
            config_cache_path=Path(env.get("SS_CONFIG_CACHE", str(outbox.with_name("edge_config.json")))),
            device_code=env.get("SS_DEVICE_CODE") or None,
            log_level=env.get("LOG_LEVEL", "INFO").upper(),
            go2rtc_url=env.get("GO2RTC_URL", ""),
        )
