# Vision models

The edge code never downloads models. Put the files on the edge box and point the env vars at them.
Only permissive licences: **Apache-2.0, MIT or BSD**. Do **not** use Ultralytics YOLO (v5/v8/v11, AGPL-3.0)
weights or export code without a commercial licence (TRD §8).

| Use | Model | Licence | Env var | Status in code |
|---|---|---|---|---|
| Person + phone detection | **YOLOX** (Megvii) s / m | Apache-2.0 | `SS_DETECTOR_MODEL` | Supported (`ONNXDetector`) |
| Person + phone detection, alternative | **RT-DETR** (lyuwenyu/RT-DETR, PaddleDetection) | Apache-2.0 | – | Needs an output adapter (different ONNX outputs) |
| Body + hand keypoints | **MediaPipe Pose Landmarker** lite/full | Apache-2.0 | `SS_POSE_MODEL` | Supported (`MediaPipePose`) |
| Body keypoints, alternative | **RTMPose** (MMPose) | Apache-2.0 | – | Implement the `PoseEstimator` protocol |
| Demo without a model | OpenCV HOG people detector | Apache-2.0 (OpenCV 4.5+) | – | Built in; persons only, no phones |

COCO already has `person` (class 0) and `cell phone` (class 67), so a COCO-pretrained YOLOX works for a
demo. For production, fine-tune on factory frames (plan §7) with hard negatives: scissors, tape, ID cards,
machine parts that look like phones.

## YOLOX → ONNX

```bash
git clone https://github.com/Megvii-BaseDetection/YOLOX && cd YOLOX
pip install -v -e .
# COCO weights: yolox_s.pth from the repo's release page (or your fine-tuned checkpoint)
python tools/export_onnx.py --output-name yolox_s.onnx -n yolox-s -c yolox_s.pth
# fine-tuned: python tools/export_onnx.py --output-name factory.onnx -f exps/your_exp.py -c best_ckpt.pth
```

Next to the `.onnx` put a JSON with the same name (`yolox_s.json`):

```json
{
  "format": "yolox",
  "input_size": [640, 640],
  "decoded": false,
  "classes": {"0": "person", "67": "phone"},
  "model_version": "yolox-s-coco-v1"
}
```

- `decoded`: `false` for the default export (the edge decodes the grid); `true` if exported with `--decode_in_inference`.
- `classes`: model class index → `person` / `phone`. Other classes are ignored. A fine-tuned 2-class model is `{"0": "person", "1": "phone"}`.
- `model_version` is stored on every event, so a rollback is "deploy the previous file".
- Preprocessing matches YOLOX: BGR, 0–255, no mean/std, letterbox at top-left, pad value 114.

## MediaPipe Pose Landmarker

Download `pose_landmarker_lite.task` (or `_full`) from the MediaPipe model page
(<https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker>) and set
`SS_POSE_MODEL=/models/pose_landmarker_lite.task`. It runs on each person crop, one pose per person.

## RT-DETR / RTMPose (later)

- RT-DETR: `tools/export_onnx.py` in lyuwenyu/RT-DETR produces `labels, boxes, scores` with an
  `orig_target_sizes` input. Add a small `RTDETRDetector` that returns `Detection` objects; the rest of the
  pipeline does not change.
- RTMPose: export with MMDeploy to ONNX (`rtmpose-t/s`, SimCC head) and implement `PoseEstimator.estimate`
  returning the keypoint names used in `vision/observe.py` (`nose`, ears, wrists).

## Acceptance before going live (PRD §8)

Run new models in **observation mode** first. Targets: presence ≥ 98 %, working vs not working ≥ 85 %,
phone use precision ≥ 90 % against supervisor-reviewed samples.
