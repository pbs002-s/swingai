# StitchSense edge box

Software that runs on the factory floor. It turns sensor messages and camera frames into events and
pushes them to the central API (`POST /api/v1/ingest/events`). Raw video never leaves the box. Only
small, blurred evidence stills are written, and only for events that need review.

```
ESP32 sensors ──MQTT──> Mosquitto ──> collector ──┐
                                                  ├─> SQLite outbox (WAL) ──> sender ──HTTPS──> central API
IP cameras ──RTSP──> vision pipeline ─────────────┘
```

| Folder | What it is |
|---|---|
| `collector/` | `main.py` (asyncio service), `outbox.py` (SQLite outbox, 72 h retention), `sender.py` (batches of up to 500, backoff with jitter, per-row results), `mqtt_bridge.py` (topics → events, machine state on change only), `control.py` (heartbeat 30 s, `GET /edge/config` every 5 min, tolerates 404), `events.py` (event schema + local validation) |
| `vision/` | `rules.py` (per-station state machine, pure), `observe.py` (detections + pose → observation), `detector.py` (YOLOX ONNX, NMS, HOG demo fallback, MediaPipe pose), `zones.py` (polygons, privacy masks, blur), `pipeline.py` (capture + sampling + evidence), `MODELS.md` |
| `firmware/` | ESP32 sketches: `machine_sensor` (SCT-013 current clamp), `needle_sensor` (stroke-synced needle presence) |
| `tests/` | pytest; no network, broker, camera, GPU or model files needed |

## What the vision rules emit

`worker_state` transitions only: `working`, `idle`, `phone_use`, `away`, `break`, `uncertain`.
`phone_use` always goes to supervisor review with one blurred still. The system only knows a worker is
**away** from the station; it never guesses where they went. An absence gets its reason from the
personal-break allowance, a supervisor reason code, or a card tap (plan §3.3), all on the central side.

## Environment

| Variable | Used by | Default | Meaning |
|---|---|---|---|
| `SS_API_URL` | collector | `http://localhost:8000` | Central server base URL (use `https://` outside dev) |
| `SS_DEVICE_TOKEN` | collector | required | The edge box's device token (Admin → Devices) |
| `SS_DEVICE_CODE` | collector | – | Sent as `source_device_code` on sensor events |
| `MQTT_HOST` / `MQTT_PORT` | both | `localhost` / `1883` | Mosquitto on the edge box. Vision reads machine state from it if `MQTT_HOST` is set |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | both | empty | Broker credentials |
| `OUTBOX_PATH` | both | `data/outbox.sqlite3` | Shared SQLite outbox |
| `SS_CONFIG_CACHE` | collector | next to the outbox | Last config from `GET /api/v1/edge/config` |
| `SS_DETECTOR_MODEL` | vision | – | YOLOX `.onnx` (+ `.json` class map next to it). Unset = HOG demo detector |
| `SS_POSE_MODEL` | vision | – | MediaPipe `pose_landmarker_*.task`. Unset = no hands / phone judgement |
| `EVIDENCE_DIR` | vision | `data` | Where blurred evidence JPEGs go (`evidence/YYYY/MM/DD/<uuid>.jpg`) |
| `LOG_LEVEL` | both | `INFO` | Logs are JSON lines on stdout |

## Run locally against the dev API

```bash
cd edge
uv sync                       # core + dev (collector, tests)
uv sync --extra vision        # + OpenCV, ONNX Runtime, MediaPipe for the camera pipeline

# A device token for the seeded edge box EDGE-1. There is no rotate-token endpoint yet, so set the hash
# directly in the dev database (dev only!):
#   UPDATE devices SET token_hash = encode(sha256('dev-edge-token'::bytea), 'hex') WHERE code = 'EDGE-1';

# Mosquitto for sensors (or skip it; the collector keeps retrying the broker)
docker run --rm -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf

SS_API_URL=http://localhost:8000 SS_DEVICE_TOKEN=dev-edge-token SS_DEVICE_CODE=EDGE-1 \
  uv run python -m collector.main

# Fake a sensor
mosquitto_pub -t factory/L1-S01/machine/state -m '{"running": true, "current_a": 1.8}'

# Camera pipeline: replay a video in real time (writes to the same outbox); --dry-run only logs
uv run python -m vision.pipeline --config vision/demo_config.json --demo sample.mp4 --dry-run
uv run python -m vision.pipeline --config vision/demo_config.json --source rtsp://user:pass@cam/stream1
uv run python -m vision.pipeline --config vision/demo_config.json --source 0   # webcam
```

`vision/demo_config.json` shows the camera config: stations with normalised (0–1) `work_zone` /
`hands_zone` polygons, as drawn in the web "Add camera" wizard, plus privacy masks, fps, break windows
(factory local time), face blur, and rule thresholds. Once `GET /edge/config` exists it will supply these;
until then the file is the source.

Tests and lint:

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format .
```

## Docker Compose (edge box)

`docker-compose.yml` runs Mosquitto, the collector and the vision pipeline, sharing one outbox volume.

```bash
cp .env.example .env                       # fill SS_DEVICE_TOKEN, MQTT_PASSWORD, CAMERA_RTSP_URL
docker run --rm -v "$PWD/mosquitto:/m" eclipse-mosquitto:2 \
  sh -c 'mosquitto_passwd -b -c /m/passwd collector "<password>" && mosquitto_passwd -b /m/passwd sensor "<password>"'
mkdir -p models config && cp vision/demo_config.json config/camera.json   # then edit zones
# put yolox_s.onnx + yolox_s.json + pose_landmarker_lite.task in models/ (see vision/MODELS.md)
docker compose up -d
```

One vision container per camera (copy the service with its own config and RTSP URL). Run chrony (NTP)
on the host: the server rejects events far in the future and flags clock skew.

## Delivery guarantees

- Every event is written to the outbox with its UUID before any network call; re-sends are safe
  (the API answers `duplicate`).
- Rows leave the outbox only on a 2xx with per-row `accepted` / `duplicate`. `rejected` rows are parked
  with the error code (`UNKNOWN_STATION`, `DEVICE_STATION_MISMATCH`, …) and never resent.
- Network errors, 5xx, 401/403/404 and 429 (honours `Retry-After`) back off from 1 s to 5 min with jitter.
- Rows older than 72 h are dropped with a logged count.

## Live view (factory LAN only)

`go2rtc` re-serves each camera so browsers on the factory network can watch it. The collector registers every camera from the pulled config (`GO2RTC_URL`). To enable the Live cameras page for a box, set `live_base` in that edge box device's config on the central server to the box's LAN address, e.g. `http://192.168.20.5:1984`. Do not forward ports 1984 or 8555 to the internet. Camera passwords never reach the browser.
