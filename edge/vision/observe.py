"""Turn one frame's detections + poses into a per-station Observation for the rules. Pure numpy/python.

Heuristics (tune in the pilot; all positions in pixels of the original frame):
- the operator is the highest-scoring person whose box centre is inside the station's work zone;
- hands at work = a visible wrist / index-finger keypoint inside the hands zone (None when no pose);
- phone in hand = a phone box within reach of a wrist (or inside the operator box when there is no pose);
- head down to phone = nose clearly below the ear line, or the phone close to the face.
Detections whose centre is inside a privacy mask are dropped: masked areas are never analysed.
"""

import math
from collections.abc import Sequence
from datetime import datetime

from vision.detector import Detection, Pose
from vision.rules import Observation
from vision.zones import Polygon, StationZone, in_any, point_in_polygon

KEYPOINT_MIN_SCORE = 0.3
HAND_POINTS = ("left_wrist", "right_wrist", "left_index", "right_index")


def _norm(pt: tuple[float, float], w: int, h: int) -> tuple[float, float]:
    return pt[0] / w, pt[1] / h


def visible_detections(dets: Sequence[Detection], masks: Sequence[Polygon], w: int, h: int) -> list[Detection]:
    return [d for d in dets if not in_any(*_norm(d.center, w, h), masks)]


def _kp(pose: Pose | None, name: str) -> tuple[float, float] | None:
    if pose is None or name not in pose.keypoints:
        return None
    x, y, s = pose.keypoints[name]
    return (x, y) if s >= KEYPOINT_MIN_SCORE else None


def _inside(box: Sequence[float], pt: tuple[float, float], pad: float = 0.0) -> bool:
    x1, y1, x2, y2 = box
    return x1 - pad <= pt[0] <= x2 + pad and y1 - pad <= pt[1] <= y2 + pad


def _head_down(pose: Pose | None, phone: Detection, person_h: float) -> bool:
    nose = _kp(pose, "nose")
    if nose is None:
        return False
    ears = [p for p in (_kp(pose, "left_ear"), _kp(pose, "right_ear")) if p]
    if ears and nose[1] - sum(e[1] for e in ears) / len(ears) > 0.03 * person_h:
        return True
    return math.dist(nose, phone.center) < 0.25 * person_h


def build_observation(
    zone: StationZone,
    persons: Sequence[tuple[Detection, Pose | None]],
    phones: Sequence[Detection],
    frame_wh: tuple[int, int],
    ts: datetime,
    machine_running: bool | None = None,
    scheduled_break: bool = False,
) -> Observation:
    w, h = frame_wh
    here = [(d, p) for d, p in persons if point_in_polygon(*_norm(d.center, w, h), zone.work_zone)]
    if not here:
        return Observation(ts, False, machine_running=machine_running, scheduled_break=scheduled_break)
    person, pose = max(here, key=lambda dp: dp[0].score)
    person_h = person.box[3] - person.box[1]

    hand_pts = [pt for name in HAND_POINTS if (pt := _kp(pose, name))]
    hands = (
        None
        if pose is None or not pose.keypoints
        else any(point_in_polygon(*_norm(pt, w, h), zone.hands_zone) for pt in hand_pts)
    )

    phone, head_down = None, False
    for ph in sorted(phones, key=lambda d: d.score, reverse=True):
        reach = 0.2 * person_h
        held = any(math.dist(pt, ph.center) < reach for pt in hand_pts) if hand_pts else _inside(person.box, ph.center)
        if held:
            phone, head_down = ph, _head_down(pose, ph, person_h)
            break
    return Observation(
        ts,
        True,
        hands_in_work_zone=hands,
        phone_in_hand=phone is not None,
        phone_confidence=phone.score if phone else 0.0,
        head_down_to_phone=head_down,
        machine_running=machine_running,
        scheduled_break=scheduled_break,
    )
