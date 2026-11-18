"""Register each camera from the pulled config as a go2rtc stream so browsers on the factory LAN can watch it live.

Camera passwords stay on this box: the browser only ever gets the go2rtc player URL.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)


def rtsp_url(conn: dict[str, Any]) -> str:
    auth = f"{quote(conn['username'], safe='')}:{quote(conn.get('password', ''), safe='')}@" if conn.get("username") else ""
    return f"rtsp://{auth}{conn['host']}:{conn.get('port', 554)}{conn.get('rtsp_path', '/')}"


async def register_streams(client: httpx.AsyncClient, go2rtc_url: str, cameras: list[dict[str, Any]]) -> int:
    """PUT one stream per camera (idempotent, so it also heals a go2rtc restart). Returns how many succeeded."""
    done = 0
    for cam in cameras:
        if not cam.get("connection"):
            continue
        try:
            resp = await client.put(
                f"{go2rtc_url.rstrip('/')}/api/streams", params={"name": cam["code"], "src": rtsp_url(cam["connection"])}
            )
            done += resp.is_success
        except httpx.HTTPError as exc:
            log.warning("go2rtc register %s failed: %s", cam["code"], exc.__class__.__name__)
    return done
