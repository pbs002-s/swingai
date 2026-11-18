"""Station zones and privacy masks. Polygons are stored normalised (0-1 of width/height), as drawn in the
web "Add camera" wizard (VISION_AND_SENSING_PLAN §6.2), and converted to pixels per frame size.

Privacy masks are never analysed (detections inside them are dropped) and are always blurred, along
with heads, on any evidence image before it is written to disk.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

Point = tuple[float, float]
Polygon = list[Point]


def parse_polygon(raw: Sequence[Sequence[float]]) -> Polygon:
    """Validate a normalised polygon: at least 3 points, each coordinate within 0..1."""
    poly = [(float(p[0]), float(p[1])) for p in raw]
    if len(poly) < 3:
        raise ValueError("polygon needs at least 3 points")
    if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in poly):
        raise ValueError("polygon points must be normalised to 0..1")
    return poly


def point_in_polygon(x: float, y: float, poly: Sequence[Point]) -> bool:
    """Ray casting (even-odd rule). Points exactly on an edge may fall either way."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def to_pixels(poly: Sequence[Point], width: int, height: int) -> np.ndarray:
    return np.array([[round(x * (width - 1)), round(y * (height - 1))] for x, y in poly], dtype=np.int32)


@dataclass(frozen=True)
class StationZone:
    station_code: str
    work_zone: Polygon  # the station: a person here is "at the station"
    hands_zone: Polygon  # needle / fabric area: wrists here count as hands at work

    @classmethod
    def from_dict(cls, data: dict) -> "StationZone":
        work = parse_polygon(data["work_zone"])
        return cls(data["station_code"], work, parse_polygon(data["hands_zone"]) if data.get("hands_zone") else work)


def in_any(x: float, y: float, polys: Sequence[Polygon]) -> bool:
    return any(point_in_polygon(x, y, p) for p in polys)


def head_box(person_box: Sequence[float], fraction: float = 0.3) -> tuple[float, float, float, float]:
    """Upper part of a person box, used to blur heads without any face detection."""
    x1, y1, x2, y2 = person_box
    return x1, y1, x2, y1 + (y2 - y1) * fraction


def blur_regions(
    frame: np.ndarray, boxes: Sequence[Sequence[float]], masks: Sequence[Polygon], kernel: int = 51
) -> np.ndarray:
    """Return a copy of `frame` with pixel boxes (x1, y1, x2, y2) and normalised mask polygons blurred."""
    import cv2

    h, w = frame.shape[:2]
    region = np.zeros((h, w), dtype=np.uint8)
    for x1, y1, x2, y2 in boxes:
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(np.ceil(x2))), min(h, int(np.ceil(y2)))
        region[y1:y2, x1:x2] = 255
    for poly in masks:
        cv2.fillPoly(region, [to_pixels(poly, w, h)], 255)
    if not region.any():
        return frame.copy()
    k = max(kernel, w // 15) | 1  # scale with frame so faces stay unreadable at 4K; must be odd
    blurred = cv2.GaussianBlur(frame, (k, k), 0)
    out = frame.copy()
    out[region > 0] = blurred[region > 0]
    return out
