"""Register each camera from the pulled config as a go2rtc stream so browsers on the factory LAN can watch it live.

Camera passwords stay on this box: the browser only ever gets the go2rtc player URL.
Privacy zones are painted black here, before go2rtc serves the picture, and audio is dropped. A camera with
privacy zones is never registered as a raw stream: if the masked source cannot be built it is not served at all.
"""

import logging
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

MIN_SIDE = 0.005  # a degenerate zone still gets a visible box


def rtsp_url(conn: dict[str, Any]) -> str:
    auth = ""
    if conn.get("username"):
        auth = f"{quote(conn['username'], safe='')}:{quote(conn.get('password', ''), safe='')}@"
    return f"rtsp://{auth}{conn['host']}:{conn.get('port', 554)}{conn.get('rtsp_path', '/')}"


def _clamp(v: float) -> float:
    return min(1.0, max(0.0, float(v)))


def privacy_boxes(zones: Sequence[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """Bounding box (x, y, w, h, 0-1) of each privacy polygon. It always covers the polygon, so it only hides more."""
    boxes = []
    for z in zones:
        if z.get("kind") != "privacy" or len(z.get("points", [])) < 3:
            continue
        xs, ys = [_clamp(p[0]) for p in z["points"]], [_clamp(p[1]) for p in z["points"]]
        x0, y0 = min(xs), min(ys)
        boxes.append((x0, y0, max(max(xs) - x0, MIN_SIDE), max(max(ys) - y0, MIN_SIDE)))
    return boxes


def mask_filter(boxes: Sequence[tuple[float, float, float, float]]) -> str:
    """ffmpeg -vf value with no spaces, sized from the frame itself (iw, ih) so it fits any resolution."""
    return ",".join(
        f"drawbox=x=iw*{x:.4f}:y=ih*{y:.4f}:w=iw*{w:.4f}:h=ih*{h:.4f}:color=black:t=fill" for x, y, w, h in boxes
    )


def stream_source(cam: dict[str, Any]) -> str:
    """The go2rtc source: the plain RTSP URL when nothing needs hiding, else an ffmpeg-masked, silent one."""
    url = rtsp_url(cam["connection"])
    boxes = privacy_boxes(cam.get("zones") or [])
    if not boxes:
        return url
    return (
        f"exec:ffmpeg -hide_banner -loglevel error -rtsp_transport tcp -i {url} -vf {mask_filter(boxes)} "
        "-an -c:v libx264 -preset ultrafast -tune zerolatency -g 30 -f rtsp {output}"
    )


async def register_streams(
    client: httpx.AsyncClient, go2rtc_url: str, cameras: list[dict[str, Any]], auth: tuple[str, str] | None = None
) -> int:
    """PUT one stream per camera (idempotent, so it also heals a go2rtc restart). Returns how many succeeded."""
    done = 0
    for cam in cameras:
        if not cam.get("connection"):
            continue
        try:
            params = {"name": cam["code"], "src": stream_source(cam)}
            resp = await client.put(f"{go2rtc_url.rstrip('/')}/api/streams", params=params, auth=auth)
            done += resp.is_success
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            log.warning("go2rtc register %s failed: %s", cam.get("code"), exc.__class__.__name__)
    return done
