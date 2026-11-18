import json

import numpy as np
import pytest

from vision.detector import ModelSpec, letterbox_params, nms, postprocess_yolox, yolox_grid_decode

CLASSES = {0: "person", 67: "phone"}


def row(cx, cy, w, h, obj, cls, score, n_cls=80):
    r = np.zeros(5 + n_cls, dtype=np.float32)
    r[:5] = (cx, cy, w, h, obj)
    r[5 + cls] = score
    return r


def test_nms_keeps_best_and_drops_overlaps():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 10, 10], [20, 20, 30, 30]], dtype=np.float32)
    scores = np.array([0.8, 0.9, 0.7], dtype=np.float32)
    assert nms(boxes, scores, 0.5) == [1, 2]
    assert nms(boxes, scores, 0.99) == [1, 0, 2]


def test_letterbox_params_fit_aspect():
    assert letterbox_params(1080, 1920, (640, 640)) == (pytest.approx(1 / 3), 360, 640)
    assert letterbox_params(640, 640, (640, 640)) == (1.0, 640, 640)


def test_postprocess_scales_filters_and_nms_per_class():
    pred = np.stack(
        [
            row(320, 180, 100, 200, 0.9, 0, 0.9),  # person
            row(322, 182, 100, 200, 0.9, 0, 0.8),  # duplicate person -> suppressed
            row(322, 182, 20, 30, 0.9, 67, 0.8),  # phone overlapping the person -> kept (other class)
            row(100, 100, 50, 50, 0.9, 2, 0.99),  # car -> not in class map
            row(500, 300, 50, 50, 0.2, 0, 0.5),  # low score
        ]
    )
    scale = 1 / 3  # 1920x1080 frame letterboxed into 640x640
    dets = postprocess_yolox(pred, scale, CLASSES, (1080, 1920), score_threshold=0.3)
    assert [d.label for d in dets] == ["person", "phone"]
    person = dets[0]
    assert person.score == pytest.approx(0.81)
    assert person.box == pytest.approx((810, 240, 1110, 840))


def test_postprocess_clips_and_handles_empty():
    assert postprocess_yolox(np.zeros((0, 85), np.float32), 1.0, CLASSES, (100, 100)) == []
    dets = postprocess_yolox(np.stack([row(5, 5, 20, 20, 1, 0, 1)]), 1.0, CLASSES, (100, 100))
    assert dets[0].box == (0.0, 0.0, 15.0, 15.0)


def test_yolox_grid_decode_first_and_last_cells():
    size = (64, 64)
    n = sum((64 // s) ** 2 for s in (8, 16, 32))
    raw = np.zeros((n, 6), dtype=np.float32)
    out = yolox_grid_decode(raw, size)
    assert out.shape == (n, 6)
    assert out[0, :4].tolist() == [0, 0, 8, 8]  # cell (0,0), stride 8, exp(0) * 8
    assert out[-1, :4].tolist() == [32, 32, 32, 32]  # last stride-32 cell (1,1)


def test_model_spec_reads_class_map_next_to_model(tmp_path):
    model = tmp_path / "yolox_s.onnx"
    (tmp_path / "yolox_s.json").write_text(
        json.dumps(
            {
                "format": "yolox",
                "input_size": [416, 416],
                "classes": {"0": "person", "67": "phone"},
                "model_version": "yolox-s-coco",
            }
        )
    )
    spec = ModelSpec.load(model)
    assert spec.classes == CLASSES and spec.input_size == (416, 416) and spec.model_version == "yolox-s-coco"
    (tmp_path / "yolox_s.json").write_text(json.dumps({"format": "rtdetr", "classes": {}}))
    with pytest.raises(ValueError):
        ModelSpec.load(model)
