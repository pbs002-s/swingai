"""Person / phone detection and pose. Heavy libraries (onnxruntime, cv2, mediapipe) are imported lazily,
so the pure parts (letterbox maths, YOLOX decoding, NMS) run and test with numpy only.

Models must be Apache-2.0 / MIT / BSD (see vision/MODELS.md). No Ultralytics/AGPL weights.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

YOLOX_STRIDES = (8, 16, 32)
YOLOX_PAD_VALUE = 114


@dataclass(frozen=True)
class Detection:
    label: str  # "person" | "phone"
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in original frame pixels

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2


@dataclass(frozen=True)
class Pose:
    keypoints: dict[str, tuple[float, float, float]] = field(default_factory=dict)  # name -> (x px, y px, score)


class Detector(Protocol):
    model_version: str

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class PoseEstimator(Protocol):
    def estimate(self, frame: np.ndarray, person_boxes: list[tuple[float, float, float, float]]) -> list[Pose]: ...


# ---- pure post-processing -------------------------------------------------------------------------


def letterbox_params(h: int, w: int, size: tuple[int, int]) -> tuple[float, int, int]:
    """Scale that fits (h, w) inside size (H, W) keeping aspect, and the resized height/width.
    YOLOX pads bottom/right (image at top-left), so no offset is needed to undo it."""
    scale = min(size[0] / h, size[1] / w)
    return scale, round(h * scale), round(w * scale)


def letterbox(frame: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, float]:
    import cv2

    scale, nh, nw = letterbox_params(frame.shape[0], frame.shape[1], size)
    out = np.full((size[0], size[1], 3), YOLOX_PAD_VALUE, dtype=np.uint8)
    out[:nh, :nw] = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out, scale


def yolox_grid_decode(raw: np.ndarray, size: tuple[int, int], strides: tuple[int, ...] = YOLOX_STRIDES) -> np.ndarray:
    """Decode raw YOLOX head output (N, 5+C) exported without --decode_in_inference into input pixels."""
    grids, expanded = [], []
    for s in strides:
        gh, gw = size[0] // s, size[1] // s
        xv, yv = np.meshgrid(np.arange(gw), np.arange(gh))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        expanded.append(np.full((gh * gw, 1), s))
    grid, stride = np.concatenate(grids), np.concatenate(expanded)
    out = raw.astype(np.float32).copy()
    out[:, :2] = (out[:, :2] + grid) * stride
    out[:, 2:4] = np.exp(out[:, 2:4]) * stride
    return out


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy non-maximum suppression on xyxy boxes; returns kept indexes, best first."""
    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        w = np.maximum(0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        h = np.maximum(0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = w * h
        iou = inter / np.maximum(areas[i] + areas[rest] - inter, 1e-9)
        order = rest[iou <= iou_threshold]
    return keep


def postprocess_yolox(
    pred: np.ndarray,
    scale: float,
    classes: dict[int, str],
    frame_hw: tuple[int, int],
    score_threshold: float = 0.3,
    iou_threshold: float = 0.45,
) -> list[Detection]:
    """pred: decoded (N, 5+C) rows of cx, cy, w, h, objectness, class scores, in letterboxed pixels."""
    cls_ids = pred[:, 5:].argmax(1)
    scores = pred[:, 4] * pred[np.arange(len(pred)), 5 + cls_ids]
    wanted = np.isin(cls_ids, list(classes)) & (scores >= score_threshold)
    pred, cls_ids, scores = pred[wanted], cls_ids[wanted], scores[wanted]
    if not len(pred):
        return []
    cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
    boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1) / scale
    h, w = frame_hw
    boxes = np.clip(boxes, 0, [w, h, w, h])
    offset = cls_ids[:, None] * (max(h, w) + 1)  # class-wise NMS in one pass
    keep = nms(boxes + offset, scores, iou_threshold)
    return [Detection(classes[int(cls_ids[i])], float(scores[i]), tuple(float(v) for v in boxes[i])) for i in keep]


# ---- runtime implementations ----------------------------------------------------------------------


@dataclass(frozen=True)
class ModelSpec:
    """Read from <model>.json next to the .onnx file."""

    classes: dict[int, str]
    input_size: tuple[int, int] = (640, 640)
    decoded: bool = False
    model_version: str = "unknown"

    @classmethod
    def load(cls, model_path: Path) -> "ModelSpec":
        data = json.loads(model_path.with_suffix(".json").read_text(encoding="utf-8"))
        if data.get("format", "yolox") != "yolox":
            raise ValueError("only YOLOX-format ONNX output is supported; see vision/MODELS.md")
        return cls(
            classes={int(k): v for k, v in data["classes"].items()},
            input_size=tuple(data.get("input_size", (640, 640))),
            decoded=bool(data.get("decoded", False)),
            model_version=data.get("model_version", model_path.stem),
        )


class ONNXDetector:
    def __init__(self, model_path: str | Path, score_threshold: float = 0.3, iou_threshold: float = 0.45):
        import onnxruntime as ort

        path = Path(model_path)
        self.spec = ModelSpec.load(path)
        self.model_version = self.spec.model_version
        providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        self.session = ort.InferenceSession(str(path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.score_threshold, self.iou_threshold = score_threshold, iou_threshold

    def detect(self, frame: np.ndarray) -> list[Detection]:
        img, scale = letterbox(frame, self.spec.input_size)  # BGR, 0-255: what YOLOX was trained on
        blob = np.ascontiguousarray(img.transpose(2, 0, 1)[None], dtype=np.float32)
        pred = self.session.run(None, {self.input_name: blob})[0][0]
        if not self.spec.decoded:
            pred = yolox_grid_decode(pred, self.spec.input_size)
        return postprocess_yolox(
            pred, scale, self.spec.classes, frame.shape[:2], self.score_threshold, self.iou_threshold
        )


class HOGPersonDetector:
    """Model-free fallback for demos: OpenCV's built-in HOG people detector. Persons only, no phones."""

    model_version = "opencv-hog-demo"

    def __init__(self) -> None:
        import cv2

        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame: np.ndarray) -> list[Detection]:
        rects, weights = self.hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        if not len(rects):
            return []
        boxes = np.array([[x, y, x + w, y + h] for x, y, w, h in rects], dtype=np.float32)
        scores = np.clip(np.asarray(weights, dtype=np.float32).ravel(), 0, 1)
        return [
            Detection("person", float(scores[i]), tuple(float(v) for v in boxes[i])) for i in nms(boxes, scores, 0.4)
        ]


MEDIAPIPE_LANDMARKS = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_index": 19,
    "right_index": 20,
}


class MediaPipePose:
    """MediaPipe Pose Landmarker (Apache-2.0, Tasks API), run on each person crop so every pose maps to
    one detected person. Needs the `pose_landmarker_lite.task` model file (see MODELS.md)."""

    def __init__(self, model_path: str | Path, min_confidence: float = 0.5):
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as exc:
            raise RuntimeError("mediapipe is not installed: uv sync --extra vision") from exc
        if not Path(model_path).is_file():
            raise RuntimeError(f"pose model not found: {model_path}")
        self._mp = mp
        options = mp_vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=min_confidence,
        )
        self.landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    def estimate(self, frame: np.ndarray, person_boxes: list[tuple[float, float, float, float]]) -> list[Pose]:
        import cv2

        poses = []
        for x1, y1, x2, y2 in person_boxes:
            x1, y1, x2, y2 = (max(0, int(v)) for v in (x1, y1, x2, y2))
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                poses.append(Pose())
                continue
            rgb = np.ascontiguousarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            result = self.landmarker.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
            if not result.pose_landmarks:
                poses.append(Pose())
                continue
            lm = result.pose_landmarks[0]
            ch, cw = crop.shape[:2]
            points = {
                n: (x1 + lm[i].x * cw, y1 + lm[i].y * ch, lm[i].visibility) for n, i in MEDIAPIPE_LANDMARKS.items()
            }
            poses.append(Pose(points))
        return poses
