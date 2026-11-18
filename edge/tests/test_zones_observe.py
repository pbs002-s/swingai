from datetime import UTC, datetime

import numpy as np
import pytest

from vision.detector import Detection, Pose
from vision.observe import build_observation, visible_detections
from vision.zones import StationZone, head_box, parse_polygon, point_in_polygon, to_pixels

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
TS = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
W, H = 1000, 1000


def test_point_in_polygon_square_and_concave():
    assert point_in_polygon(0.5, 0.5, SQUARE)
    assert not point_in_polygon(1.5, 0.5, SQUARE)
    l_shape = [(0, 0), (1, 0), (1, 0.4), (0.4, 0.4), (0.4, 1), (0, 1)]
    assert point_in_polygon(0.2, 0.8, l_shape)
    assert not point_in_polygon(0.8, 0.8, l_shape)


def test_parse_polygon_validates():
    assert parse_polygon([[0, 0], [1, 0], [0, 1]]) == [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    with pytest.raises(ValueError):
        parse_polygon([[0, 0], [1, 1]])
    with pytest.raises(ValueError):
        parse_polygon([[0, 0], [1.2, 0], [0, 1]])


def test_to_pixels_maps_normalised_corners():
    assert to_pixels(SQUARE, 640, 480).tolist() == [[0, 0], [639, 0], [639, 479], [0, 479]]


def test_station_zone_defaults_hands_zone_to_work_zone():
    z = StationZone.from_dict({"station_code": "L1-S01", "work_zone": SQUARE})
    assert z.hands_zone == z.work_zone


def test_head_box_is_upper_part_of_person():
    assert head_box((10, 100, 50, 300)) == (10, 100, 50, 160)


def test_privacy_mask_drops_detections():
    mask = [[(0.0, 0.0), (0.2, 0.0), (0.2, 1.0), (0.0, 1.0)]]
    inside, outside = Detection("person", 0.9, (0, 0, 100, 100)), Detection("person", 0.9, (500, 500, 600, 600))
    assert visible_detections([inside, outside], mask, W, H) == [outside]


def test_blur_regions_changes_only_masked_pixels():
    cv2 = pytest.importorskip("cv2")
    from vision.zones import blur_regions

    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    out = blur_regions(frame, [(0, 0, 50, 50)], [[(0.75, 0.75), (1.0, 0.75), (1.0, 1.0), (0.75, 1.0)]])
    assert not np.array_equal(out[:50, :50], frame[:50, :50])
    assert not np.array_equal(out[160:, 160:], frame[160:, 160:])
    assert np.array_equal(out[80:120, 80:120], frame[80:120, 80:120])
    assert cv2 is not None


# ---- observations -------------------------------------------------------------------------------

ZONE = StationZone.from_dict(
    {
        "station_code": "L1-S01",
        "work_zone": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
        "hands_zone": [[0.1, 0.6], [0.4, 0.6], [0.4, 0.9], [0.1, 0.9]],
    }
)
PERSON = Detection("person", 0.9, (100, 100, 400, 900))  # centre (250, 500): inside work zone


def pose(wrist=(250, 700), nose=(250, 200), ears=(180, 250)):
    return Pose({"left_wrist": (*wrist, 0.9), "nose": (*nose, 0.9), "left_ear": (*ears, 0.9)})


def test_absent_when_no_person_in_zone():
    other = Detection("person", 0.9, (600, 100, 900, 900))
    obs = build_observation(ZONE, [(other, None)], [], (W, H), TS, machine_running=True)
    assert obs.person_in_zone is False and obs.machine_running is True


def test_hands_in_work_zone_from_wrist():
    obs = build_observation(ZONE, [(PERSON, pose())], [], (W, H), TS)
    assert obs.person_in_zone and obs.hands_in_work_zone is True and not obs.phone_in_hand


def test_hands_unknown_without_pose():
    obs = build_observation(ZONE, [(PERSON, None)], [], (W, H), TS)
    assert obs.hands_in_work_zone is None


def test_phone_in_hand_near_wrist_with_head_down():
    phone = Detection("phone", 0.88, (220, 400, 280, 460))  # centre (250, 430)
    obs = build_observation(ZONE, [(PERSON, pose(wrist=(250, 440)))], [phone], (W, H), TS)
    assert obs.phone_in_hand and obs.phone_confidence == pytest.approx(0.88)
    assert obs.hands_in_work_zone is False
    assert obs.head_down_to_phone is False  # nose above ear line and far from the phone
    obs = build_observation(
        ZONE, [(PERSON, pose(wrist=(250, 440), nose=(250, 300), ears=(180, 250)))], [phone], (W, H), TS
    )
    assert obs.head_down_to_phone is True


def test_phone_far_from_hands_is_not_in_hand():
    phone = Detection("phone", 0.9, (380, 850, 400, 870))
    obs = build_observation(ZONE, [(PERSON, pose(wrist=(250, 300)))], [phone], (W, H), TS)
    assert not obs.phone_in_hand
