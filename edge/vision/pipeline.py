"""Camera pipeline: capture -> sample at N fps -> detect + pose -> per-station rules -> outbox.

    uv run python -m vision.pipeline --config vision/demo_config.json --source rtsp://user:pass@cam/stream
    uv run python -m vision.pipeline --config vision/demo_config.json --demo sample.mp4 [--dry-run]

Detector: ONNX model from SS_DETECTOR_MODEL (YOLOX format, see MODELS.md); without one, OpenCV's
HOG people detector is used (persons only, no phone use). Pose: MediaPipe, model from SS_POSE_MODEL.
Only state changes are emitted. phone_use events get one evidence JPEG with heads and privacy masks
blurred before it is written; raw frames are never stored.
"""

import argparse
import json
import logging
import os
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from collector.events import make_event
from collector.outbox import Outbox
from vision.detector import Detector, PoseEstimator
from vision.observe import build_observation, visible_detections
from vision.rules import Observation, RulesConfig, StationRules, Transition
from vision.zones import Polygon, StationZone, blur_regions, head_box, parse_polygon

log = logging.getLogger("vision")
RECONNECT_MAX_S = 30.0


@dataclass(frozen=True)
class VisionConfig:
    device_code: str
    stations: list[StationZone]
    privacy_masks: list[Polygon] = field(default_factory=list)
    fps: float = 5.0
    timezone: str = "Asia/Dhaka"
    breaks: list[tuple[dtime, dtime]] = field(default_factory=list)
    face_blur: bool = True
    rules: RulesConfig = field(default_factory=RulesConfig)

    @classmethod
    def load(cls, path: str | Path) -> "VisionConfig":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        fps = float(d.get("fps", 5))
        if not 0 < fps <= 30:
            raise ValueError("fps must be within (0, 30]")
        ZoneInfo(d.get("timezone", "Asia/Dhaka"))  # fail fast on a bad zone name
        return cls(
            device_code=d["device_code"],
            stations=[StationZone.from_dict(s) for s in d["stations"]],
            privacy_masks=[parse_polygon(m) for m in d.get("privacy_masks", [])],
            fps=fps,
            timezone=d.get("timezone", "Asia/Dhaka"),
            breaks=[(dtime.fromisoformat(b["start"]), dtime.fromisoformat(b["end"])) for b in d.get("breaks", [])],
            face_blur=bool(d.get("face_blur", True)),
            rules=RulesConfig.from_dict(d.get("rules")),
        )

    def in_break(self, ts: datetime) -> bool:
        local = ts.astimezone(ZoneInfo(self.timezone)).time()
        return any(s <= local < e if s <= e else local >= s or local < e for s, e in self.breaks)


class MachineStates:
    """Latest machine running flag per station, from the same MQTT topic the collector reads."""

    def __init__(self) -> None:
        self.running: dict[str, bool] = {}
        self._lock = threading.Lock()

    def get(self, station: str) -> bool | None:
        with self._lock:
            return self.running.get(station)

    def start(self, host: str, port: int, username: str = "", password: str = "") -> Any:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"stitchsense-vision-{os.getpid()}")
        if username:
            client.username_pw_set(username, password)

        def on_message(_c: Any, _u: Any, msg: Any) -> None:
            try:
                running = json.loads(msg.payload).get("running")
            except (ValueError, AttributeError):
                return
            if isinstance(running, bool):
                with self._lock:
                    self.running[msg.topic.split("/")[1]] = running

        client.on_connect = lambda c, *_: c.subscribe("factory/+/machine/state", 1)
        client.on_message = on_message
        client.connect_async(host, port, keepalive=30)
        client.loop_start()
        return client


class Pipeline:
    def __init__(
        self,
        cfg: VisionConfig,
        detector: Detector,
        pose: PoseEstimator | None,
        outbox: Outbox | None,
        evidence_dir: Path,
        machines: MachineStates | None = None,
    ):
        self.cfg, self.detector, self.pose, self.outbox = cfg, detector, pose, outbox
        self.evidence_dir, self.machines = evidence_dir, machines
        self.rules = {s.station_code: StationRules(cfg.rules) for s in cfg.stations}

    def process(self, frame: np.ndarray | None, ts: datetime) -> list[dict[str, Any]]:
        """Run one sampled frame (None = no picture) through every station; return emitted events."""
        brk = self.cfg.in_break(ts)
        if frame is None:
            return self._feed(
                {s.station_code: Observation(ts, None, scheduled_break=brk) for s in self.cfg.stations}, None, [], ts
            )
        h, w = frame.shape[:2]
        dets = visible_detections(self.detector.detect(frame), self.cfg.privacy_masks, w, h)
        person_dets = [d for d in dets if d.label == "person"]
        phones = [d for d in dets if d.label == "phone"]
        poses = self.pose.estimate(frame, [d.box for d in person_dets]) if self.pose and person_dets else []
        persons = list(zip(person_dets, poses or [None] * len(person_dets), strict=True))
        obs = {
            z.station_code: build_observation(
                z,
                persons,
                phones,
                (w, h),
                ts,
                machine_running=self.machines.get(z.station_code) if self.machines else None,
                scheduled_break=brk,
            )
            for z in self.cfg.stations
        }
        return self._feed(obs, frame, [d.box for d in person_dets], ts)

    def _feed(self, obs: dict, frame: np.ndarray | None, person_boxes: list, ts: datetime) -> list[dict[str, Any]]:
        events = []
        for code, o in obs.items():
            tr = self.rules[code].update(o)
            if tr is not None:
                events.append(self._emit(code, tr, frame, person_boxes))
        return events

    def _emit(self, station: str, tr: Transition, frame: np.ndarray | None, person_boxes: list) -> dict[str, Any]:
        event = make_event(
            "worker_state",
            tr.state,
            station,
            tr.start_time,
            confidence=tr.confidence,
            model_version=self.detector.model_version,
            metadata=dict(tr.metadata),
            source_device_code=self.cfg.device_code,
        )
        if tr.needs_review and frame is not None:
            event["metadata"]["evidence_keys"] = [
                self._save_evidence(event["event_uuid"], tr.start_time, frame, person_boxes)
            ]
        log.info("station %s -> %s since %s (conf %s)", station, tr.state, event["start_time"], tr.confidence)
        if self.outbox is not None:
            self.outbox.add(event)
        return event

    def _save_evidence(self, event_uuid: str, at: datetime, frame: np.ndarray, person_boxes: list) -> str:
        import cv2

        heads = [head_box(b) for b in person_boxes] if self.cfg.face_blur else []
        safe = blur_regions(frame, heads, self.cfg.privacy_masks)
        key = f"evidence/{at:%Y/%m/%d}/{event_uuid}.jpg"
        path = self.evidence_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), safe, [cv2.IMWRITE_JPEG_QUALITY, 85]):
            log.error("could not write evidence %s", path)
        return key


def _open(source: str) -> Any:
    import cv2

    if source.isdigit():
        return cv2.VideoCapture(int(source))
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    return cv2.VideoCapture(source, cv2.CAP_FFMPEG)


def run_live(pipe: Pipeline, source: str, stop: threading.Event) -> None:
    """Live camera: read continuously (keeps the decoder current), analyse at cfg.fps, reconnect on loss."""
    period, next_at, delay = 1 / pipe.cfg.fps, 0.0, 1.0
    cap = _open(source)
    while not stop.is_set():
        ok, frame = cap.read()
        now = time.monotonic()
        if not ok:
            pipe.process(None, datetime.now(UTC))  # camera blind -> uncertain, never a guess
            log.warning("camera read failed; reconnecting in %.0f s", delay)
            cap.release()
            stop.wait(delay)
            delay = min(delay * 2, RECONNECT_MAX_S)
            cap = _open(source)
            continue
        delay = 1.0
        if now >= next_at:
            next_at = now + period
            pipe.process(frame, datetime.now(UTC))
    cap.release()


def run_demo(pipe: Pipeline, path: str, stop: threading.Event) -> int:
    """Replay a video file at real speed; timestamps are wall-clock from the start of the replay."""
    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit(f"cannot open video {path}")
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(video_fps / pipe.cfg.fps))
    t0, wall0, i, emitted = datetime.now(UTC), time.monotonic(), 0, 0
    while not stop.is_set():
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            offset = i / video_fps
            stop.wait(max(0.0, offset - (time.monotonic() - wall0)))
            emitted += len(pipe.process(frame, t0 + timedelta(seconds=offset)))
        i += 1
    cap.release()
    log.info("demo finished: %d frames, %d events", i, emitted)
    return emitted


def build_detector() -> Detector:
    from vision.detector import HOGPersonDetector, ONNXDetector

    model = os.environ.get("SS_DETECTOR_MODEL")
    if model:
        return ONNXDetector(model)
    log.warning("SS_DETECTOR_MODEL not set: using the HOG person detector (demo only, no phone detection)")
    return HOGPersonDetector()


def build_pose() -> PoseEstimator | None:
    from vision.detector import MediaPipePose

    model = os.environ.get("SS_POSE_MODEL")
    if not model:
        log.warning("SS_POSE_MODEL not set: pose disabled, so hands at work and phone use cannot be judged")
        return None
    try:
        return MediaPipePose(model)
    except RuntimeError as exc:
        log.warning("pose disabled: %s", exc)
        return None


def main() -> None:
    from collector.main import setup_logging

    ap = argparse.ArgumentParser(description="StitchSense edge vision")
    ap.add_argument("--config", required=True, help="camera/station JSON (see vision/demo_config.json)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--source", help="RTSP URL, video file, or webcam index")
    src.add_argument("--demo", metavar="VIDEO", help="replay a video file in real time")
    ap.add_argument("--dry-run", action="store_true", help="log events, do not write the outbox")
    args = ap.parse_args()

    setup_logging(os.environ.get("LOG_LEVEL", "INFO").upper())
    cfg = VisionConfig.load(args.config)
    outbox = None if args.dry_run else Outbox(os.environ.get("OUTBOX_PATH", "data/outbox.sqlite3"))
    machines = None
    if os.environ.get("MQTT_HOST"):
        machines = MachineStates()
        machines.start(
            os.environ["MQTT_HOST"],
            int(os.environ.get("MQTT_PORT", "1883")),
            os.environ.get("MQTT_USERNAME", ""),
            os.environ.get("MQTT_PASSWORD", ""),
        )
    pipe = Pipeline(cfg, build_detector(), build_pose(), outbox, Path(os.environ.get("EVIDENCE_DIR", "data")), machines)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())  # docker stop
    try:
        if args.demo:
            run_demo(pipe, args.demo, stop)
        else:
            run_live(pipe, args.source, stop)
    except KeyboardInterrupt:
        stop.set()
    finally:
        if outbox is not None:
            outbox.close()


if __name__ == "__main__":
    main()
