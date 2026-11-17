# Vision and Sensing Plan

**Audience:** development team and project owner
**Status:** Plan only — nothing here is built yet. 2026-11-17
**Related:** [PRD](PRD.md) · [TRD](TRD.md) · [Deployment Requirements](DEPLOYMENT_REQUIREMENTS.md) · [API](API.md)

This plan answers four questions:

1. How do we detect worker activity: working, phone use, away from the station?
2. How do we detect needle breaks?
3. How do we detect seam defects: skipped stitches, puckering and flagging?
4. How does an admin connect a camera from the web app?

It also covers which languages, tools and AI models we use, and how we train them.

> "Flaggering" in the request is read as **flagging**: the fabric lifting with the needle on its upstroke, which causes skipped stitches. Correct this if something else was meant.

---

## 1. The approach in one paragraph

Each problem gets the evidence source that can actually see it. Cameras watch people and finished seams. Sensors watch fast, hidden mechanical events like needle breaks. Records and human review confirm the rest.

We do **not** train AI models from scratch. We start from open, commercially licensed pretrained models and **fine-tune them on each factory's own labelled images** (transfer learning). A rule layer combines model outputs with machine signals and the shift schedule.

Nothing in the real-time loop sends video to an outside AI service. Everything runs on the factory's edge box.

## 2. Languages and tools

| Layer | Language | Main tools | Why |
|---|---|---|---|
| Edge vision service | **Python 3.12** | OpenCV, GStreamer (RTSP decode), ONNX Runtime / TensorRT (inference), NumPy | Standard computer-vision ecosystem; runs on Jetson or a GPU mini PC |
| Model training | **Python** | PyTorch, MMDetection / MMPose, Anomalib, scikit-learn | Fine-tuning detectors, pose and anomaly models |
| Labelling | — | CVAT or Label Studio (open source, self-hosted) | Images never leave the factory |
| Sensor firmware | **C++** (Arduino core or ESP-IDF on ESP32) | Interrupts, timers, MQTT client | Microsecond timing for needle-stroke sensing |
| Edge messaging | — | Mosquitto (MQTT) | Sensors → edge box |
| Backend API | **Python** (FastAPI) | As in the TRD | Same language as vision; receives events |
| Web app | **TypeScript** (Next.js) | As in the TRD | Camera setup wizard, zone drawing, review queue |

### Models (all permissive licences: Apache-2.0 / MIT / BSD)

| Task | Starting model | Fine-tuned on |
|---|---|---|
| Person and phone detection | RT-DETR or YOLOX (pretrained on COCO, which already has a "cell phone" class) | Factory frames: workers, phones, fabric, machine parts that look like phones |
| Body and hand pose | RTMPose (MMPose) or MediaPipe Pose/Hands | Usually works without fine-tuning; fine-tune only if accuracy is low |
| Seam anomaly (puckering, other defects) | PatchCore or PaDiM (Anomalib) | **Good seams only**, per fabric and operation |
| Skipped-stitch classifier | Small CNN (e.g. ResNet-18 / MobileNetV3) + classical stitch-spacing measurement | Labelled close-up seam images, good and defective |
| Needle-break vibration (optional) | 1D CNN or autoencoder on vibration spectra | Recorded normal running + logged breaks |

Do **not** bundle Ultralytics YOLO (AGPL-3.0) without buying its commercial licence (TRD §8).

## 3. Worker activity: working, phone use, away

### 3.1 Signals combined

| Signal | Source | What it tells us |
|---|---|---|
| Person in station zone | Camera → person detector + zone polygon | Present / absent |
| Hands in the work area | Camera → pose model (wrists and hands inside the needle / fabric zone) | Handling fabric or not |
| Machine running | Clamp-on current sensor | Motor running / stopped |
| Phone in hand | Camera → phone detector + hand keypoints near the phone + head turned down to it | Possible phone use |
| Production confirmed | Hourly output entry / counts | Work actually completed |
| Schedule | Shift policy | Break, lunch, work time |

### 3.2 Decision rules (per station, about 5 frames per second)

```
if scheduled break                          -> BREAK
elif person absent from zone > 60 s         -> AWAY
elif phone detected in hand
     AND (hands out of work zone OR machine stopped)
     for >= 20 s with confidence >= 0.75    -> POSSIBLE PHONE USE (goes to review)
elif hands in work zone OR machine running  -> WORKING
elif present, hands idle, machine stopped
     for > idle threshold (e.g. 5 min)      -> IDLE
else                                        -> UNCERTAIN
```

- All thresholds come from the factory's policy settings, not code.
- A state only changes when the new state holds for a few seconds (hysteresis), so one bad frame does not flip it.
- The phone rule needs the phone **and** a sign that work stopped. A phone resting on the table while the worker sews is not phone use.
- Every phone event goes to the supervisor review queue with one or two still images (faces blurred). The system never records phone use as fact by itself.

### 3.3 Washroom and other absences: what we will and will not do

**The system will never detect "washroom".** No camera is allowed in or near a washroom, and the system must not guess where a person went. It only knows that the worker is **away from the station**.

How an absence gets its reason:

1. **Personal-break allowance** in the shift policy, e.g. up to 20 minutes per shift of short absences counted as an authorised break, not idle. Set per factory.
2. **Supervisor reason code** on the station timeline: personal break, called by supervisor, fetching material, training, medical.
3. **Optional card tap** at the station: a tap on leaving and on return closes the gap automatically, with no reason recorded.

Absences beyond the allowance with no reason show as "Away, no reason". That is an indicator for the supervisor to look at, never a penalty by itself.

### 3.4 Camera placement for activity

- One camera per 1–2 stations, mounted 2.5–3 m high, angled down at about 45° from the operator's front or side, so hands, the work area and the table top are visible.
- Each station gets a zone polygon drawn in the web app (§6).
- No faces needed. Face blur is applied on the edge box before any image is stored.

## 4. Needle-break detection

### 4.1 Why the camera alone fails

A sewing needle is about 1 mm thick and moves 20–70 strokes per second. Normal CCTV at 25–30 fps sees a blur, and the needle is hidden by the presser foot and fabric. The camera is supporting evidence only.

### 4.2 Methods, in order of preference

| # | Method | How it works | Effort | Status |
|---|---|---|---|---|
| 1 | **Machine controller signal** | Some modern servo-motor controllers report stop or error states. Read them where the machine exposes them | Low if available | Check per machine model in the site survey |
| 2 | **Needle-presence sensor, synced to the stroke** | A small optical or inductive sensor aims at the point where the needle tip should be at the bottom of each stroke. A Hall sensor or the motor's sync signal tells the ESP32 when each stroke happens. If the tip is missing for N strokes in a row while the machine runs → **needle break** | Medium; needs mounting per machine type | **Main pilot method** |
| 3 | **Vibration signature** | An accelerometer (e.g. ADXL345) on the machine head. A break changes the vibration pattern; an anomaly model flags it | Medium; noisy | Secondary signal |
| 4 | **Stop pattern + replacement log** | Machine stops, then a needle change is logged for that machine. The system asks maintenance to confirm the reason | Low | Available from R2, no extra hardware |
| 5 | **Operator / supervisor report** | One tap: "needle broke" | Low | Always available |

**Plan:** start R2 with methods 4 and 5, which give ground truth (every replaced needle records why it was removed). In parallel, prototype method 2 on two machines with a machine technician. Measure its precision and recall against the logged breaks for 4 weeks before rolling it out.

### 4.3 What the needle sensor firmware does (ESP32, C++)

```
on stroke interrupt (Hall sensor or motor sync):
    wait a calibrated delay to the bottom of the stroke
    read needle-presence sensor
    if machine running and tip not seen: missing += 1 else missing = 0
    if missing >= N (e.g. 5):
        publish factory/<station>/needle/alarm {type: "suspected_break"}
        missing = 0
```

The event goes to review as **suspected break**. Maintenance confirms it when the needle is replaced, and only then does it count in the needle-batch statistics.

## 5. Seam defects: skipped stitch, puckering, flagging

### 5.1 Where to inspect

Inspecting seams **at the sewing machine while the fabric moves** is hard: the needle and presser foot hide the stitch, and the fabric moves fast. The plan has two stages:

| Stage | Where | Hardware | When |
|---|---|---|---|
| A. QC table | End-of-line or in-line quality station: the inspector lays the panel or garment flat under a fixed camera | Fixed industrial or 4K camera, diffuse LED panel light, a marked placement area | R4, first |
| B. Inline | Just behind the presser foot on selected machines | Global-shutter industrial camera, macro lens, ring light, mounted after the needle | Later, only where stage A proves the models |

### 5.2 Skipped stitch

**What it looks like:** a gap where a stitch should be. The thread spans two stitch lengths, or a loop is missing.

**Detection:**

1. Find the seam line (edge and thread segmentation; classical CV first).
2. Measure the stitch spacing along the seam. The intensity pattern along a good seam repeats at the stitch length (e.g. 3 mm). An FFT or peak detection finds the spacing.
3. A gap longer than about 1.5× the expected stitch length = **possible skipped stitch**.
4. A small CNN classifier checks the crop around the gap, to reject folds, prints and lint.

The expected stitch length (stitches per inch) comes from the operation's settings, so the same model works across operations.

### 5.3 Puckering

**What it looks like:** wrinkles or waves along the seam after sewing.

**Detection:** an anomaly-detection model (PatchCore / PaDiM) trained **only on good seams** of the same fabric and operation. Anything that looks unlike a good seam scores high. Optionally a grading model maps the score to the 1–5 seam-smoothness scale quality teams already use. Low-angle (raking) light makes wrinkles cast shadows and much easier to see. This is the main reason for controlled lighting.

Why anomaly detection: factories have thousands of good seams but few labelled defects. These models need only good examples to start.

### 5.4 Flagging

**What it is:** the fabric lifts with the needle on the upstroke, so the loop does not form and stitches are skipped. It is a **cause**, not something left visible on the seam.

**Detection: indirect, by pattern.**

- Skipped stitches clustered on one machine and fabric, especially light or stretch fabrics, point to flagging.
- The system then suggests checks to maintenance: presser-foot pressure, needle size, needle-plate hole, thread tension.
- Seeing flagging directly would need a high-speed side camera at the needle (hundreds of fps). That is a research option, not in the plan.

### 5.5 Output and review

Each inspected item returns one of: no visible defect · possible skipped stitch · possible puckering · other seam defect · image not suitable · needs human inspection. Defects go to the quality inspector's review queue with the crop highlighted. Confirmed results become `inspection_defects` and new training labels.

## 6. Connecting a camera from the web app

### 6.1 Network principle

Cameras sit on an isolated camera VLAN with no internet access. **Only the edge box talks to cameras.** The central server cannot reach the factory network directly (it may be in the cloud, behind NAT). So the web app asks the edge box to do camera work through a **job queue**:

```
Web app → API: "discover cameras on EDGE-1"
API stores job → Edge box polls GET /edge/jobs every few seconds
Edge box runs the job on the camera network → POST /edge/jobs/{id}/result
Web app shows the result
```

### 6.2 "Add camera" wizard (Admin → Devices → Add camera)

| Step | Screen | What happens |
|---|---|---|
| 1. Edge box | Choose which edge box the camera connects to | Lists online edge boxes |
| 2. Find camera | **Scan network** (ONVIF discovery: lists brand, model, IP) **or** enter it manually: IP, port, RTSP path, username, password | Edge box runs ONVIF WS-Discovery; manual entry for cameras without ONVIF |
| 3. Test | **Test connection** | Edge opens the RTSP stream and returns one snapshot, resolution, frame rate, codec and latency. A clear error if it fails: wrong password, unreachable, unsupported codec |
| 4. Assign | Pick one or two stations this camera covers | Station list filtered by line |
| 5. Draw zones | On the snapshot: work zone per station (polygon), hand/needle area, **privacy masks** (aisles, other areas, always blurred and never analysed) | Saved as polygons in the device config |
| 6. Purpose and settings | Purpose: activity or seam inspection · analysis rate (default 5 fps) · face blur (default on) · evidence retention | Values from the factory's policy, editable |
| 7. Save and verify | Camera shows **Online** with live fps and last frame time; a 30-second "test detection" shows boxes on the snapshot | Edge box picks up the config on its next poll |

Also on the Devices page: edit zones, replace camera (keeps station history), disable, view health (fps, dropped frames, last seen), and the "device offline" alert rule.

Sensors (ESP32) use a similar **Add sensor** flow: the device shows a QR code or ID, the admin scans or types it, assigns the machine and station, and runs a test ("turn the machine on now" → the running signal must appear).

### 6.3 Security

- Camera passwords are encrypted at rest on the server and sent only to the edge box over TLS. They are never shown again after saving.
- Snapshots in the wizard are short-lived (signed URL, 5 minutes) and not stored.
- Opening an evidence image is written to the audit log.
- Cameras need RTSP and, ideally, ONVIF Profile S. Buy cameras with both.

### 6.4 API additions (to be added to [API.md](API.md) when built)

| Method | Path | Purpose |
|---|---|---|
| POST | `/edge-boxes/{id}/jobs` | Create a job: `discover_cameras`, `test_camera`, `snapshot` |
| GET | `/edge-boxes/{id}/jobs/{job_id}` | Job status and result (web app polls) |
| GET | `/edge/jobs` | Edge box fetches pending jobs (device token) |
| POST | `/edge/jobs/{job_id}/result` | Edge box returns a result |
| POST | `/devices` (kind `camera`) | Save camera: edge box, connection (password encrypted), stations, purpose |
| PUT | `/devices/{id}/zones` | Save zones and privacy masks (polygons in image coordinates, 0–1) |
| POST | `/devices/{id}/test-detection` | 30-second test run; returns an annotated snapshot |

## 7. How the models get trained and improved

```
1. Site survey + consent  →  2. Record sample video (observation mode)
        ↓
3. Label in CVAT / Label Studio (on-prem)  →  4. Fine-tune in PyTorch on a GPU workstation
        ↓
5. Validate on held-out days  →  6. Export to ONNX / TensorRT  →  7. Deploy to edge in observation mode
        ↓
8. Supervisor reviews (confirm / reject) become new labels  →  back to 4
```

- **Observation mode:** a new model's events are stored but hidden from scores and alerts until it meets its targets.
- **Model versions:** every event stores the model version. Rolling back = deploying the previous version.
- **Active learning:** rejected events are the most useful training data. The review queue feeds them back automatically.
- **Per-factory tuning:** a base model is shared across installs; each factory gets a light fine-tune on its own lighting, fabrics and uniforms. Training data stays in that factory unless the client agrees otherwise in writing.

### Rough data needs (estimates, to confirm in the pilot)

| Model | Starting data |
|---|---|
| Person / phone detector fine-tune | 2,000–5,000 labelled frames across shifts and lighting, including hard negatives (scissors, tape, ID cards) |
| Seam anomaly (puckering) | 200–500 good-seam images per fabric × operation, plus 30–50 defect images to set thresholds |
| Skipped-stitch classifier | 300+ defect crops and 1,000+ good crops |
| Needle-break sensor | No ML at first: timing rule plus about 4 weeks of logged breaks to tune N and validate |

### Acceptance targets before going live (from PRD §8)

| Detection | Target |
|---|---|
| Presence | ≥ 98% accuracy |
| Working vs not working | ≥ 85% against reviewed samples |
| Phone use | precision ≥ 90% (recall reported) |
| Needle break (sensor) | precision ≥ 90%, recall ≥ 80% against the replacement log |
| Skipped stitch / puckering | Set with the quality team during the pilot |

## 8. What is not used, and why

| Option | Decision |
|---|---|
| Training models from scratch | No. Too much data needed; fine-tuning pretrained models is faster and more accurate |
| Cloud AI or vision-language APIs on live video | No. Privacy, cost, latency and factory internet. A vision-language model may later help **label** data offline, on-prem only |
| Face recognition to identify workers | No. Identity comes from assignment and card tap (PRD §7.2) |
| Audio | No |
| Cameras in washrooms, prayer or break rooms | Never |

## 9. Where this sits in the releases

| Release | Sensing work |
|---|---|
| R2 | Current sensor (machine running), needle-break logging (methods 4 + 5), "Add sensor" flow, needle-presence sensor prototype on 2 machines |
| R3 | "Add camera" wizard, zones, edge vision: presence, working, phone use, away; labelling and training pipeline |
| R4 | QC-table seam inspection: skipped stitch, puckering; flagging pattern suggestions; inline seam camera trial |
