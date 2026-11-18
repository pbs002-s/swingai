from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from collector.outbox import Outbox
from vision.detector import Detection, Pose
from vision.pipeline import Pipeline, VisionConfig

CONFIG = Path(__file__).resolve().parents[1] / "vision" / "demo_config.json"
T0 = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)  # 09:00 in Dhaka


class FakeDetector:
    model_version = "fake-1"

    def detect(self, frame):
        return [
            Detection("person", 0.9, (300, 200, 500, 900)),  # L1-S01 (x 0.15-0.6)
            Detection("person", 0.9, (20, 200, 120, 900)),
        ]  # inside the privacy mask: ignored


class FakePose:
    def estimate(self, frame, boxes):
        return [Pose({"left_wrist": (400, 700, 0.9)}) for _ in boxes]


def test_demo_config_loads_and_knows_breaks():
    cfg = VisionConfig.load(CONFIG)
    assert [s.station_code for s in cfg.stations] == ["L1-S01", "L1-S02"]
    assert cfg.in_break(T0 + timedelta(hours=4, minutes=30))  # 13:30 Dhaka
    assert not cfg.in_break(T0)


def test_pipeline_emits_state_changes_into_outbox(tmp_path):
    cfg = VisionConfig.load(CONFIG)
    box = Outbox(":memory:")
    pipe = Pipeline(cfg, FakeDetector(), FakePose(), box, tmp_path)
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    events = []
    for i in range(5 * 70):  # 70 s at 5 fps
        events += pipe.process(frame, T0 + timedelta(seconds=i / 5))
    states = {(e["station_code"], e["state"]) for e in events}
    assert states == {("L1-S01", "working"), ("L1-S02", "away")}
    assert all(e["model_version"] == "fake-1" and e["source_device_code"] == "CAM-L1-S01" for e in events)
    assert box.counts()["pending"] == 2


def test_no_frame_means_uncertain(tmp_path):
    pipe = Pipeline(VisionConfig.load(CONFIG), FakeDetector(), None, None, tmp_path)
    events = []
    for i in range(20):
        events += pipe.process(None, T0 + timedelta(seconds=i / 5))
    assert {e["state"] for e in events} == {"uncertain"}
