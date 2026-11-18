"""Cameras and the edge job queue (docs/VISION_AND_SENSING_PLAN.md §6).

The central server cannot reach the camera VLAN, so camera work (discover, test, snapshot, test detection)
is queued here and done by the edge box, which polls GET /edge/jobs with its device token.
Camera passwords are Fernet-encrypted at rest and leave the server only via GET /edge/config and /edge/jobs.
"""

import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import time
from datetime import timedelta
from typing import Annotated, Any, Literal

from cryptography.fernet import Fernet
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.db import SessionLocal, get_session, utcnow
from app.core.errors import AppError, not_found, ok
from app.core.security import client_ip, current_device, require_roles
from app.models import Device, Line, Station, User
from app.models.edge import JOB_KINDS, EdgeJob

log = logging.getLogger("stitchsense.cameras")
router = APIRouter(tags=["cameras"])

ONLINE_WINDOW = timedelta(minutes=3)
SIM_DELAY_S = 1.5  # simulated edge answers after a short pause so the wizard shows its progress state
MAX_RESULT_BYTES = 256 * 1024
_DEV_SECRET = "stitchsense-dev-only-secrets-key"  # noqa: S105 - dev/test fallback, refused in production
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)
_NO_CTRL = r"^[^\x00-\x1f\x7f]*$"

admin_only = require_roles("factory_admin")
admin_or_maint = require_roles("factory_admin", "maintenance")
live_viewers = require_roles("factory_admin", "supervisor", "management")


# ---------- secrets ----------
def _load_fernet() -> Fernet:
    raw = os.environ.get("SS_SECRETS_KEY", "")
    if not raw:
        if get_settings().env == "production":
            raise RuntimeError("SS_SECRETS_KEY is required in production (32+ random characters)")
        log.warning("SS_SECRETS_KEY is not set; using a fixed development key. Never do this in production.")
        raw = _DEV_SECRET
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


_fernet = _load_fernet()


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


# ---------- schemas ----------
class ConnectionIn(BaseModel):
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=554, ge=1, le=65535)
    rtsp_path: str = Field(default="/", max_length=255, pattern=r"^/[^\s\x00-\x1f\x7f]*$")
    username: str = Field(default="", max_length=64, pattern=_NO_CTRL)
    password: str = Field(default="", max_length=128, pattern=_NO_CTRL)

    @field_validator("host")
    @classmethod
    def _host(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError:
            if not _HOSTNAME.match(v):
                raise ValueError("host must be an IP address or a hostname") from None
        return v

    def stored(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"password"})
        return {**data, "password_enc": encrypt(self.password) if self.password else None}


def public_connection(conn: dict[str, Any] | None) -> dict[str, Any] | None:
    if not conn:
        return None
    return {k: conn.get(k) for k in ("host", "port", "rtsp_path", "username")} | {"has_password": bool(conn.get("password_enc"))}


def edge_connection(conn: dict[str, Any] | None) -> dict[str, Any] | None:
    """Connection for the edge box only: password decrypted."""
    if not conn:
        return None
    enc = conn.get("password_enc")
    return {k: conn.get(k) for k in ("host", "port", "rtsp_path", "username")} | {"password": decrypt(enc) if enc else ""}


class JobParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection: ConnectionIn | None = None
    camera_id: int | None = None


class JobIn(BaseModel):
    kind: Literal["discover_cameras", "test_camera", "snapshot", "test_detection"]
    params: JobParams = Field(default_factory=JobParams)

    @model_validator(mode="after")
    def _needs(self) -> "JobIn":
        p = self.params
        if self.kind == "test_detection" and p.camera_id is None:
            raise ValueError("test_detection needs params.camera_id")
        if self.kind in ("test_camera", "snapshot") and p.connection is None and p.camera_id is None:
            raise ValueError(f"{self.kind} needs params.connection or params.camera_id")
        return self


class JobResultIn(BaseModel):
    status: Literal["done", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=500)


Purpose = Literal["activity", "seam_inspection"]
StationIds = Annotated[list[int], Field(min_length=1, max_length=2)]


def _unique(ids: list[int] | None) -> list[int] | None:
    if ids is not None and len(set(ids)) != len(ids):
        raise ValueError("station_ids must not repeat")
    return ids


class CameraIn(BaseModel):
    edge_box_id: int
    name: str = Field(min_length=1, max_length=80, pattern=_NO_CTRL)
    connection: ConnectionIn
    station_ids: StationIds
    purpose: Purpose = "activity"
    fps: int = Field(default=5, ge=1, le=15)
    face_blur: bool = True

    @field_validator("station_ids")
    @classmethod
    def _no_repeat(cls, v: list[int] | None) -> list[int] | None:
        return _unique(v)


class CameraPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80, pattern=_NO_CTRL)
    purpose: Purpose | None = None
    fps: int | None = Field(default=None, ge=1, le=15)
    face_blur: bool | None = None
    station_ids: StationIds | None = None
    is_active: bool | None = None

    @field_validator("station_ids")
    @classmethod
    def _no_repeat(cls, v: list[int] | None) -> list[int] | None:
        return _unique(v)


Coord = Annotated[float, Field(ge=0, le=1)]


class ZoneIn(BaseModel):
    station_id: int | None = None
    kind: Literal["work", "privacy"]
    points: list[tuple[Coord, Coord]] = Field(min_length=3, max_length=32)

    @model_validator(mode="after")
    def _station(self) -> "ZoneIn":
        if self.kind == "work" and self.station_id is None:
            raise ValueError("a work zone needs a station_id")
        return self


class ZonesIn(BaseModel):
    zones: list[ZoneIn] = Field(max_length=24)


# ---------- test cameras (a laptop or phone browser camera, for lab testing only) ----------
FRAME_MAX_BYTES = 300 * 1024
FRAME_FRESH_S = 10.0
SEEN_WRITE_EVERY_S = 30.0
_frames: dict[int, tuple[bytes, float]] = {}  # ponytail: in-process, newest frame only; use a shared store if the API ever runs multi-process
_seen_written: dict[int, float] = {}


def _frame_fresh(camera_id: int) -> bool:
    frame = _frames.get(camera_id)
    return frame is not None and time.monotonic() - frame[1] < FRAME_FRESH_S


class TestSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=_NO_CTRL)


class FrameIn(BaseModel):
    jpeg: str = Field(min_length=1, max_length=FRAME_MAX_BYTES * 2)  # base64


# ---------- helpers ----------
def is_online(d: Device) -> bool:
    return d.last_seen_at is not None and d.last_seen_at > utcnow() - ONLINE_WINDOW


async def _edge_box(db: AsyncSession, box_id: int) -> Device:
    box = await db.get(Device, box_id)
    if box is None or box.kind != "edge_box" or not box.is_active:
        raise not_found("Edge box")
    return box


async def _camera(db: AsyncSession, camera_id: int) -> Device:
    cam = await db.get(Device, camera_id)
    if cam is None or cam.kind != "camera":
        raise not_found("Camera")
    return cam


async def _stations(db: AsyncSession, ids: list[int]) -> list[Station]:
    rows = {s.id: s for s in (await db.execute(select(Station).where(Station.id.in_(ids)))).scalars()}
    if any(i not in rows or rows[i].status == "inactive" for i in ids):
        raise AppError(400, "UNKNOWN_STATION", "One of the stations does not exist or is inactive.")
    return [rows[i] for i in ids]


def _station_ids(cam: Device) -> list[int]:
    return cam.config.get("station_ids") or ([cam.station_id] if cam.station_id else [])


def camera_out(cam: Device, codes: dict[int, str]) -> dict[str, Any]:
    c = cam.config
    ids = _station_ids(cam)
    return {
        "id": cam.id,
        "code": cam.code,
        "name": c.get("name", cam.code),
        "edge_box_id": c.get("edge_box_id"),
        "stations": [{"id": i, "code": codes.get(i, "?")} for i in ids],
        "purpose": c.get("purpose", "activity"),
        "fps": c.get("fps", 5),
        "face_blur": c.get("face_blur", True),
        "zones": c.get("zones", []),
        "zones_count": len(c.get("zones", [])),
        "connection": public_connection(c.get("connection")),
        "online": is_online(cam),
        "last_seen_at": cam.last_seen_at.isoformat() if cam.last_seen_at else None,
        "is_active": cam.is_active,
    }


async def _codes(db: AsyncSession, cams: list[Device]) -> dict[int, str]:
    ids = {i for c in cams for i in _station_ids(c)}
    return dict((await db.execute(select(Station.id, Station.code).where(Station.id.in_(ids)))).all()) if ids else {}


def job_out(job: EdgeJob) -> dict[str, Any]:
    params = {**job.params, "connection": public_connection(job.params.get("connection"))}
    return {
        "id": job.id,
        "edge_box_id": job.edge_device_id,
        "kind": job.kind,
        "params": params,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def finish_job(job: EdgeJob, status: str, result: dict[str, Any] | None, error: str | None) -> None:
    job.status, job.result, job.error, job.finished_at = status, result, error, utcnow()


def _require_edge(device: Device) -> Device:
    if device.kind != "edge_box":
        raise AppError(403, "DEVICE_NOT_EDGE", "Only an edge box can do this.")
    return device


async def _run_sim_later() -> None:
    from app.modules.edge_sim import run_simulated_edge_jobs  # local: edge_sim imports this module

    await asyncio.sleep(SIM_DELAY_S)
    try:
        async with SessionLocal() as db:
            await run_simulated_edge_jobs(db)
    except Exception:
        log.exception("simulated edge job run failed")


# ---------- web app side ----------
@router.get("/edge-boxes")
async def list_edge_boxes(db: AsyncSession = Depends(get_session), _: User = Depends(admin_or_maint)):
    boxes = (await db.execute(select(Device).where(Device.kind == "edge_box", Device.is_active).order_by(Device.code))).scalars()
    return ok(
        [
            {
                "id": b.id,
                "code": b.code,
                "name": b.config.get("name", b.code),
                "online": is_online(b),
                "last_seen_at": b.last_seen_at.isoformat() if b.last_seen_at else None,
            }
            for b in boxes
        ]
    )


@router.post("/edge-boxes/{box_id}/jobs", status_code=201)
async def create_job(
    box_id: int,
    body: JobIn,
    request: Request,
    tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(admin_only),
):
    box = await _edge_box(db, box_id)
    params: dict[str, Any] = {}
    if body.params.camera_id is not None:
        cam = await _camera(db, body.params.camera_id)
        if cam.config.get("edge_box_id") != box.id:
            raise AppError(400, "CAMERA_NOT_ON_EDGE", "This camera is connected to another edge box.")
        params["camera_id"] = cam.id
    if body.params.connection is not None:
        params["connection"] = body.params.connection.stored()
    job = EdgeJob(edge_device_id=box.id, kind=body.kind, params=params, status="queued", created_by=user.id)
    db.add(job)
    await db.flush()
    audit(db, user.id, "edge_job.create", "edge_job", job.id, {"kind": body.kind, "edge_box": box.code}, client_ip(request))
    await db.commit()
    if box.config.get("simulated"):
        tasks.add_task(_run_sim_later)
    return ok(job_out(job))


@router.get("/edge-boxes/{box_id}/jobs/{job_id}")
async def get_job(box_id: int, job_id: int, db: AsyncSession = Depends(get_session), _: User = Depends(admin_or_maint)):
    job = await db.get(EdgeJob, job_id)
    if job is None or job.edge_device_id != box_id:
        raise not_found("Job")
    return ok(job_out(job))


@router.get("/cameras/live")
async def live_cameras(
    request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(live_viewers)
):
    """Cameras with a player URL for the live wall. Video is served by the edge box (go2rtc) on the factory LAN,
    never by this server; a camera with no edge live_base shows a labelled simulated feed in demo mode."""
    cams = list(
        (await db.execute(select(Device).where(Device.kind == "camera", Device.is_active).order_by(Device.id))).scalars()
    )
    codes = await _codes(db, cams)
    boxes = {b.id: b for b in (await db.execute(select(Device).where(Device.kind == "edge_box"))).scalars()}
    demo = get_settings().simulator_enabled
    out = []
    for c in cams:
        base = (boxes.get(c.config.get("edge_box_id")).config.get("live_base") if c.config.get("edge_box_id") in boxes else None)
        if c.config.get("test_source"):
            live = {"mode": "frames", "url": f"/api/v1/cameras/{c.id}/frame.jpg"}
        elif base and c.config.get("connection"):
            live = {"mode": "embed", "url": f"{base.rstrip('/')}/stream.html?src={c.code}&mode=webrtc,mse"}
        elif demo:
            live = {"mode": "demo", "url": None}
        else:
            live = {"mode": "none", "url": None}
        out.append(
            {
                "id": c.id,
                "code": c.code,
                "name": c.config.get("name", c.code),
                "stations": [{"id": i, "code": codes.get(i, "?")} for i in _station_ids(c)],
                "online": _frame_fresh(c.id) if c.config.get("test_source") else is_online(c),
                "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
                "live": live,
            }
        )
    audit(db, user.id, "camera.live_view", "device", None, {"cameras": len(out)}, client_ip(request))
    await db.commit()
    return ok(out)


@router.post("/cameras/test-source", status_code=201)
async def create_test_source(
    body: TestSourceIn, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin_only)
):
    """A camera fed by a browser (laptop webcam or phone) for lab testing. Frames pass through this server's memory
    only and are never stored, but they are not face-blurred, so this is refused in production."""
    if get_settings().env == "production":
        raise AppError(403, "TEST_CAMERA_DISABLED", "Browser test cameras are not available in production.")
    cam = Device(code=f"TEST-{secrets.token_hex(3).upper()}", kind="camera", config={"name": body.name, "test_source": True})
    db.add(cam)
    await db.flush()
    audit(db, user.id, "camera.create_test_source", "device", cam.id, {"name": body.name}, client_ip(request))
    await db.commit()
    return ok({"id": cam.id, "code": cam.code, "name": body.name})


@router.put("/cameras/{camera_id}/frame")
async def put_frame(camera_id: int, body: FrameIn, db: AsyncSession = Depends(get_session), _: User = Depends(admin_only)):
    cam = await _camera(db, camera_id)
    if not cam.config.get("test_source") or not cam.is_active:
        raise AppError(400, "NOT_TEST_SOURCE", "This camera does not take browser frames.")
    try:
        jpeg = base64.b64decode(body.jpeg, validate=True)
    except ValueError:
        raise AppError(400, "BAD_FRAME", "The frame is not valid base64.") from None
    if len(jpeg) > FRAME_MAX_BYTES or not jpeg.startswith(b"\xff\xd8"):
        raise AppError(400, "BAD_FRAME", "The frame must be a JPEG under 300 KB.")
    now = time.monotonic()
    _frames[camera_id] = (jpeg, now)
    if now - _seen_written.get(camera_id, -SEEN_WRITE_EVERY_S) >= SEEN_WRITE_EVERY_S:
        _seen_written[camera_id] = now
        cam.last_seen_at = utcnow()
        await db.commit()
    return ok({"bytes": len(jpeg)})


@router.get("/cameras/{camera_id}/frame.jpg")
async def get_frame(camera_id: int, _: User = Depends(live_viewers)):
    if not _frame_fresh(camera_id):
        raise not_found("Frame")
    return Response(_frames[camera_id][0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/cameras/station-options")
async def station_options(db: AsyncSession = Depends(get_session), _: User = Depends(admin_or_maint)):
    lines = list((await db.execute(select(Line).where(Line.is_active).order_by(Line.id))).scalars())
    stations = (
        await db.execute(select(Station).where(Station.status != "inactive").order_by(Station.line_id, Station.position))
    ).scalars()
    by_line: dict[int, list[dict[str, Any]]] = {}
    for s in stations:
        by_line.setdefault(s.line_id, []).append({"id": s.id, "code": s.code, "name": s.name})
    return ok([{"id": ln.id, "code": ln.code, "name": ln.name, "stations": by_line.get(ln.id, [])} for ln in lines])


@router.get("/cameras")
async def list_cameras(db: AsyncSession = Depends(get_session), _: User = Depends(admin_or_maint)):
    cams = list((await db.execute(select(Device).where(Device.kind == "camera").order_by(Device.id))).scalars())
    codes = await _codes(db, cams)
    return ok([camera_out(c, codes) for c in cams])


@router.post("/cameras", status_code=201)
async def create_camera(
    body: CameraIn, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin_only)
):
    box = await _edge_box(db, body.edge_box_id)
    stations = await _stations(db, body.station_ids)
    cam = Device(
        code=f"CAM-{secrets.token_hex(3).upper()}",
        kind="camera",
        station_id=stations[0].id,
        config={
            "name": body.name,
            "edge_box_id": box.id,
            "station_ids": body.station_ids,
            "stations": [s.code for s in stations],
            "connection": body.connection.stored(),
            "purpose": body.purpose,
            "fps": body.fps,
            "face_blur": body.face_blur,
            "zones": [],
        },
    )
    db.add(cam)
    await db.flush()
    detail = {"name": body.name, "edge_box": box.code, "host": body.connection.host, "stations": cam.config["stations"]}
    audit(db, user.id, "camera.create", "device", cam.id, detail, client_ip(request))
    await db.commit()
    return ok(camera_out(cam, {s.id: s.code for s in stations}))


@router.patch("/cameras/{camera_id}")
async def update_camera(
    camera_id: int, body: CameraPatch, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin_only)
):
    cam = await _camera(db, camera_id)
    changes = body.model_dump(exclude_unset=True, exclude={"is_active"})
    config = {**cam.config, **changes}
    if body.station_ids is not None:
        stations = await _stations(db, body.station_ids)
        cam.station_id = stations[0].id
        config["stations"] = [s.code for s in stations]
        # a work zone for a station the camera no longer covers is meaningless
        config["zones"] = [z for z in config.get("zones", []) if z["kind"] == "privacy" or z["station_id"] in body.station_ids]
    cam.config = config
    if body.is_active is not None:
        cam.is_active = body.is_active
    audit(db, user.id, "camera.update", "device", cam.id, body.model_dump(exclude_unset=True), client_ip(request))
    await db.commit()
    return ok(camera_out(cam, await _codes(db, [cam])))


@router.put("/cameras/{camera_id}/zones")
async def put_zones(
    camera_id: int, body: ZonesIn, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin_only)
):
    cam = await _camera(db, camera_id)
    allowed = set(_station_ids(cam))
    if any(z.station_id is not None and z.station_id not in allowed for z in body.zones):
        raise AppError(400, "ZONE_STATION_NOT_ASSIGNED", "A zone names a station this camera does not cover.")
    zones = [{"station_id": z.station_id, "kind": z.kind, "points": [list(p) for p in z.points]} for z in body.zones]
    cam.config = {**cam.config, "zones": zones}
    audit(db, user.id, "camera.zones", "device", cam.id, {"zones": len(zones)}, client_ip(request))
    await db.commit()
    return ok(camera_out(cam, await _codes(db, [cam])))


@router.delete("/cameras/{camera_id}")
async def deactivate_camera(
    camera_id: int, request: Request, db: AsyncSession = Depends(get_session), user: User = Depends(admin_only)
):
    cam = await _camera(db, camera_id)
    cam.is_active = False
    audit(db, user.id, "camera.deactivate", "device", cam.id, None, client_ip(request))
    await db.commit()
    return ok({"id": cam.id, "is_active": False})


# ---------- edge box side (device token) ----------
@router.get("/edge/jobs")
async def edge_poll_jobs(device: Device = Depends(current_device), db: AsyncSession = Depends(get_session)):
    box = _require_edge(device)
    q = (
        select(EdgeJob)
        .where(EdgeJob.edge_device_id == box.id, EdgeJob.status == "queued")
        .order_by(EdgeJob.id)
        .limit(10)
        .with_for_update(skip_locked=True)
    )
    jobs = list((await db.execute(q)).scalars())
    out = []
    for job in jobs:
        job.status = "running"
        conn = job.params.get("connection")
        if conn is None and job.params.get("camera_id"):
            cam = await db.get(Device, job.params["camera_id"])
            conn = cam.config.get("connection") if cam else None
        out.append({"id": job.id, "kind": job.kind, "params": {**job.params, "connection": edge_connection(conn)}})
    box.last_seen_at = utcnow()
    await db.commit()
    return ok(out)


@router.post("/edge/jobs/{job_id}/result")
async def edge_job_result(
    job_id: int, body: JobResultIn, device: Device = Depends(current_device), db: AsyncSession = Depends(get_session)
):
    box = _require_edge(device)
    job = await db.get(EdgeJob, job_id)
    if job is None or job.edge_device_id != box.id:
        raise not_found("Job")
    if job.status in ("done", "failed"):
        raise AppError(409, "JOB_FINISHED", "This job already has a result.")
    if body.result is not None and len(json.dumps(body.result)) > MAX_RESULT_BYTES:
        raise AppError(400, "RESULT_TOO_LARGE", "The job result is too large.")
    finish_job(job, body.status, body.result, body.error)
    box.last_seen_at = utcnow()
    await db.commit()
    return ok({"id": job.id, "status": job.status})


@router.get("/edge/config")
async def edge_config(device: Device = Depends(current_device), db: AsyncSession = Depends(get_session)):
    box = _require_edge(device)
    cams = [
        c
        for c in (await db.execute(select(Device).where(Device.kind == "camera", Device.is_active))).scalars()
        if c.config.get("edge_box_id") == box.id
    ]  # ponytail: filters in Python; move to a JSON/column filter if one server holds thousands of cameras
    codes = await _codes(db, cams)
    box.last_seen_at = utcnow()
    await db.commit()
    return ok(
        {
            "edge_box": box.code,
            "cameras": [
                {
                    "id": c.id,
                    "code": c.code,
                    "name": c.config.get("name", c.code),
                    "stations": [codes.get(i) for i in _station_ids(c)],
                    "connection": edge_connection(c.config.get("connection")),
                    "purpose": c.config.get("purpose", "activity"),
                    "fps": c.config.get("fps", 5),
                    "face_blur": c.config.get("face_blur", True),
                    "zones": c.config.get("zones", []),
                }
                for c in cams
            ],
        }
    )


__all__ = ["JOB_KINDS", "decrypt", "encrypt", "finish_job", "router"]
