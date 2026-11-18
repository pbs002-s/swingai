"""Simulated edge box for demos: completes queued camera jobs for edge boxes whose config has {"simulated": true}.

Everything here is fake on purpose (cameras, snapshots, detections). A real edge box uses GET /edge/jobs.
"""

import base64
import random
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.models import Device
from app.models.edge import EdgeJob
from app.modules.cameras import decrypt, finish_job

W, H = 640, 360
_CATALOG = [
    ("Hikvision", "DS-2CD2143G2-I", "/Streaming/Channels/101"),
    ("Dahua", "IPC-HDW2431T-AS", "/cam/realmonitor?channel=1&subtype=0"),
    ("Uniview", "IPC322LB-DSF28K", "/media/video1"),
    ("Axis", "M3086-V", "/axis-media/media.amp"),
    ("Reolink", "RLC-510A", "/h264Preview_01_main"),
]
_DETECTIONS = [
    {"label": "person", "confidence": 0.94, "box": [0.31, 0.24, 0.47, 0.78]},
    {"label": "phone", "confidence": 0.71, "box": [0.43, 0.52, 0.49, 0.62]},
]


def _scene(caption: str, zones: list[dict[str, Any]], detections: list[dict[str, Any]]) -> str:
    """A monochrome isometric sewing table with an operator, as an SVG data URL (a few KB)."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="#2b2d2f"/>',
        '<g fill="none" stroke="#c9ccce" stroke-width="2" stroke-linejoin="round">',
        '<path d="M60 250 L330 120 L600 250" stroke="#55595c"/>',  # floor lines
        '<path d="M190 210 L360 140 L520 205 L350 275 Z" fill="#3a3d40"/>',  # table top
        '<path d="M190 210 V270 M350 275 V335 M520 205 V265"/>',  # legs
        '<path d="M330 175 L400 147 L450 167 L380 195 Z M380 195 V230 L450 202 V167"/>',  # machine body
        '<path d="M345 182 V215 M352 213 L370 206"/>',  # needle bar and presser foot
        '<circle cx="262" cy="118" r="20"/>',  # operator head
        '<path d="M232 230 C232 175 240 150 262 145 C286 150 296 175 296 230"/>',  # torso
        '<path d="M290 175 L330 200 M236 178 L300 215"/>',  # arms
        "</g>",
    ]
    for z in zones:
        pts = " ".join(f"{x * W:.1f},{y * H:.1f}" for x, y in z["points"])
        dash = ' stroke-dasharray="6 4"' if z["kind"] == "privacy" else ""
        fill = "#000" if z["kind"] == "privacy" else "#fff"
        parts.append(f'<polygon points="{pts}" fill="{fill}" fill-opacity="0.25" stroke="#fff" stroke-width="1.5"{dash}/>')
    for d in detections:
        x1, y1, x2, y2 = d["box"]
        label = escape(f"{d['label']} {d['confidence']:.2f}")
        parts.append(
            f'<rect x="{x1 * W:.0f}" y="{y1 * H:.0f}" width="{(x2 - x1) * W:.0f}" height="{(y2 - y1) * H:.0f}"'
            ' fill="none" stroke="#fff" stroke-width="2"/>'
            f'<rect x="{x1 * W:.0f}" y="{y1 * H - 18:.0f}" width="{len(label) * 7 + 8}" height="18" fill="#fff"/>'
            f'<text x="{x1 * W + 4:.0f}" y="{y1 * H - 5:.0f}" font-family="monospace" font-size="12" fill="#111">{label}</text>'
        )
    parts.append(
        f'<text x="12" y="{H - 12}" font-family="monospace" font-size="12" fill="#c9ccce">{escape(caption)}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode("".join(parts).encode()).decode()


def _discover(job: EdgeJob) -> dict[str, Any]:
    rng = random.Random(job.id)  # noqa: S311 - demo data
    hosts = rng.sample(range(11, 60), 4)
    picks = rng.sample(_CATALOG, rng.choice((3, 4)))
    cams = [
        {"brand": b, "model": m, "host": f"10.20.0.{h}", "port": 554, "rtsp_path": p, "onvif": True}
        for (b, m, p), h in zip(picks, hosts, strict=False)
    ]
    return {"cameras": cams}


async def _connection(db: AsyncSession, job: EdgeJob) -> tuple[dict[str, Any] | None, Device | None]:
    cam = await db.get(Device, job.params["camera_id"]) if job.params.get("camera_id") else None
    conn = job.params.get("connection") or (cam.config.get("connection") if cam else None)
    return conn, cam


async def _run(db: AsyncSession, job: EdgeJob) -> tuple[str, dict[str, Any] | None, str | None]:
    if job.kind == "discover_cameras":
        return "done", _discover(job), None
    conn, cam = await _connection(db, job)
    if conn is None:
        return "failed", None, "Camera not found."
    password = decrypt(conn["password_enc"]) if conn.get("password_enc") else ""
    if password == "wrong":  # noqa: S105 - the demo's way to show a failed login
        return "failed", None, "Authentication failed (401)"
    stamp = utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    caption = f"{conn['host']}  {stamp}"
    if job.kind == "test_detection":
        if cam is None:
            return "failed", None, "Camera not found."
        cam.last_seen_at = utcnow()
        snap = _scene(caption, cam.config.get("zones", []), _DETECTIONS)
        return "done", {"snapshot": snap, "detections": _DETECTIONS, "duration_s": 30, "fps": cam.config.get("fps", 5)}, None
    rng = random.Random(job.id)  # noqa: S311 - demo data
    info = {"resolution": "1920x1080", "width": 1920, "height": 1080, "fps": 25, "codec": "H.264"}
    return "done", {**info, "latency_ms": rng.randint(80, 180), "snapshot": _scene(caption, [], [])}, None


async def run_simulated_edge_jobs(db: AsyncSession) -> int:
    """Complete queued jobs of simulated edge boxes and keep them (and their cameras) online. Returns jobs done."""
    boxes = [
        b
        for b in (await db.execute(select(Device).where(Device.kind == "edge_box", Device.is_active))).scalars()
        if (b.config or {}).get("simulated")
    ]
    if not boxes:
        return 0
    now = utcnow()
    ids = {b.id for b in boxes}
    for b in boxes:
        b.last_seen_at = now
    for cam in (await db.execute(select(Device).where(Device.kind == "camera", Device.is_active))).scalars():
        if cam.config.get("edge_box_id") in ids:
            cam.last_seen_at = now
    q = (
        select(EdgeJob)
        .where(EdgeJob.edge_device_id.in_(ids), EdgeJob.status == "queued")
        .order_by(EdgeJob.id)
        .with_for_update(skip_locked=True)
    )
    jobs = list((await db.execute(q)).scalars())
    for job in jobs:
        finish_job(job, *(await _run(db, job)))
    await db.commit()
    return len(jobs)
