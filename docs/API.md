# API Reference

**Status:** Draft v1 — 2026-11-17
**Backend:** FastAPI (auto-generated OpenAPI at `/api/docs` stays the final source once code exists)
**Related:** [Backend Design](BACKEND_DESIGN.md) · [TRD](TRD.md) · [PRD](PRD.md)

---

## 1. Conventions

### 1.1 Base URL and versioning
```
https://<client-host>/api/v1
```
Breaking changes go to `/api/v2`; additive changes (new fields, new endpoints) stay in v1. Clients must ignore unknown fields.

### 1.2 Authentication
| Caller | Method |
|---|---|
| Web app (staff users) | Session cookie `ss_session` (httpOnly, Secure, SameSite=Lax), set by `POST /auth/login`. Every mutating request (POST/PUT/PATCH/DELETE) must send the `X-CSRF-Token` header with the value of the `ss_csrf` cookie |
| Edge collector / devices / simulator | `Authorization: Bearer <device_token>`. Only allowed on `/ingest/*` and `/edge/*` |

### 1.3 Response envelope
Every response, success or error:
```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": { "page": 1, "limit": 50, "total": 230, "request_id": "req_7f3a..." }
}
```
Error:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ASSIGNMENT_OVERLAP",
    "message": "Worker already has an assignment in this time range.",
    "details": { "conflicting_assignment_id": 812 }
  },
  "meta": { "request_id": "req_7f3a..." }
}
```
`message` is translated from `Accept-Language` (`en` or `bn`). The UI should rely on `code`, not on `message`.

### 1.4 Lists: pagination, sorting, filtering
| Param | Example | Notes |
|---|---|---|
| `page` | `1` | 1-based |
| `limit` | `50` | default 50, max 200 |
| `sort` | `-start_time,station_code` | `-` = descending |
| `q` | `rahim` | free-text search where supported |
| filters | `line_id=3&status=open` | per endpoint, listed below |
| ranges | `from=2026-11-01T00:00:00Z&to=2026-11-08T00:00:00Z` | half-open `[from, to)` |

### 1.5 Data formats
- Timestamps: ISO 8601 UTC (`2026-11-17T09:12:03Z`). Dates without time (`shift_date`) are factory-local `YYYY-MM-DD`.
- IDs: integers. Events use `event_uuid` (UUID) from the source.
- Decimals (SMV, rates) are JSON numbers.
- Bilingual names: `name` (English) + `name_bn` (Bangla, optional).

### 1.6 HTTP status codes
| Code | Use |
|---|---|
| 200 | OK (also duplicate ingest events) |
| 201 | Created |
| 202 | Accepted (async job started, e.g. reports) |
| 204 | Deleted / no content |
| 400 | Validation error (`VALIDATION_ERROR`, with field details) |
| 401 | Not logged in / bad token (`UNAUTHENTICATED`) |
| 403 | Role or scope not allowed (`FORBIDDEN`) |
| 404 | Not found, or outside the caller's scope (`NOT_FOUND`) |
| 409 | Conflict (`ASSIGNMENT_OVERLAP`, `ALREADY_REVIEWED`, `VERSION_CONFLICT`) |
| 422 | Business rule broken (`POLICY_WEIGHTS_INVALID`, `BATCH_QUARANTINED`) |
| 429 | Rate limited (`RATE_LIMITED`, `Retry-After` header) |
| 500 | Unexpected error (`INTERNAL_ERROR`, generic message only) |

### 1.7 Concurrency
Editable resources return `version` (integer). `PATCH` must send the `If-Match: <version>` header. If the version is stale, the API returns `409 VERSION_CONFLICT`. This stops two admins from overwriting each other.

### 1.8 Deletion
Master data is **deactivated**, not deleted: `PATCH {"is_active": false}`. `DELETE` exists only for records that nothing references yet; otherwise it returns `409 IN_USE`.

### 1.9 Roles (short names used below)
`SA` system admin · `FA` factory admin · `SUP` supervisor · `QM` quality · `MT` maintenance · `MG` management · `ANY` any logged-in user · `DEV` device token.
Users only see data inside their factory/line scope. Out-of-scope resources return `404`.

### 1.10 Rate limits
| Endpoint | Limit |
|---|---|
| `POST /auth/login` | 10 / min per IP + account lockout after 10 failures |
| `POST /ingest/events` | 60 requests / min per device (500 events per request) |
| Everything else | 600 / min per user |

---

## 2. Auth and session

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/auth/login` | public | Log in, sets cookies |
| POST | `/auth/logout` | ANY | End session |
| GET | `/auth/me` | ANY | Current user, roles, scopes, locale |
| POST | `/auth/change-password` | ANY | Change own password |
| PATCH | `/auth/me` | ANY | Update own `locale`, `full_name` |

`POST /auth/login`
```json
// request
{ "login": "supervisor1", "password": "••••••••" }
// 200 data
{ "user": { "id": 4, "full_name": "Karim Ahmed", "locale": "bn" },
  "roles": [ { "code": "supervisor", "scope_type": "line", "scope_id": 3 } ] }
```
Errors: `INVALID_CREDENTIALS` (401), `ACCOUNT_LOCKED` (403).

---

## 3. Users and roles

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/users` | SA, FA | List. Filters: `role`, `is_active`, `q` |
| POST | `/users` | SA | Create user |
| GET | `/users/{id}` | SA, FA | Detail |
| PATCH | `/users/{id}` | SA | Edit, deactivate |
| POST | `/users/{id}/reset-password` | SA | Set a temporary password; user must change it on next login |
| PUT | `/users/{id}/roles` | SA | Replace role list |
| GET | `/roles` | SA, FA | Role catalog |

`PUT /users/{id}/roles`
```json
[ { "role": "supervisor", "scope_type": "line", "scope_id": 3 },
  { "role": "quality", "scope_type": "factory", "scope_id": 1 } ]
```

---

## 4. Organization (factory → floor → line → station)

All are fully dynamic; there is no limit on how many exist.

| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST | `/factories` | ANY / SA | List / create |
| GET / PATCH | `/factories/{id}` | ANY / SA, FA | Detail / edit (incl. settings) |
| GET / POST | `/floors` | ANY / FA | Filter: `factory_id` |
| GET / POST | `/lines` | ANY / FA | Filter: `floor_id`, `factory_id` |
| GET / POST | `/stations` | ANY / FA | Filters: `line_id`, `status`, `q` |
| GET / PATCH | `/{floors\|lines\|stations}/{id}` | ANY / FA | Detail / edit / deactivate |
| POST | `/stations/bulk` | FA | Create many stations at once |
| POST | `/org/import` | FA | CSV import (floors, lines, stations) |
| GET | `/org/tree?factory_id=` | ANY | Full nested tree for navigation |

Factory settings (part of `PATCH /factories/{id}`):
```json
{ "name": "Unit 2", "timezone": "Asia/Dhaka",
  "settings": { "card_tap_enabled": true, "face_blur": true,
                "production_entry_interval": "hourly", "week_start": "sat" } }
```

`POST /stations/bulk` (for example, creating 100 stations on a line):
```json
{ "line_id": 3, "prefix": "L3-S", "start": 1, "count": 100, "pad": 3 }
// creates L3-S001 … L3-S100
```

---

## 5. Catalog (admin-managed lists)

Same shape for every list: `GET` (list), `POST` (create), `PATCH /{id}` (edit/deactivate).

| Path | Roles (write) | Fields |
|---|---|---|
| `/catalog/machine-types` | FA | `code`, `name`, `name_bn` |
| `/catalog/machine-brands` | FA | `name` |
| `/catalog/defect-types` | FA, QM | `code`, `name`, `name_bn`, `severity` |
| `/catalog/reason-codes` | FA | `category` (downtime/pause/reject), `code`, `name`, `name_bn` |
| `/products` | FA | `code`, `name`, `style_no` |
| `/operations` | FA | `product_id`, `code`, `name`, `smv`, `machine_type_id`, `count_unit`, `difficulty_group` (+ `POST /operations/import`) |

Read access: ANY.

---

## 6. Machines and devices

| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST | `/machines` | ANY / FA, MT | Filters: `factory_id`, `type_id`, `brand_id`, `station_id`, `status` |
| GET / PATCH | `/machines/{id}` | ANY / FA, MT | Detail / edit |
| POST | `/machines/{id}/assign` | FA, MT, SUP | Place on a station (closes previous placement) |
| GET | `/machines/{id}/history` | ANY | Placement history |
| POST | `/machines/import` | FA | CSV import |
| GET / POST | `/devices` | SA, FA | Filters: `kind`, `station_id`, `online` |
| PATCH | `/devices/{id}` | SA, FA | Mapping, config (RTSP URL, zone polygon) |
| POST | `/devices/{id}/rotate-token` | SA | New token, shown **once** |
| GET | `/devices/health` | SA, FA, MT | Online / offline, last seen, firmware |

`POST /machines/{id}/assign`
```json
{ "station_id": 41, "valid_from": "2026-11-17T02:00:00Z" }
```

---

## 7. Workers and assignments

| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST | `/workers` | ANY / FA | Filters: `line_id`, `operation_id`, `is_active`, `q` |
| GET / PATCH | `/workers/{id}` | ANY / FA | Detail / edit (incl. `rfid_card_id`) |
| POST | `/workers/import` | FA | CSV import |
| GET / PUT | `/workers/{id}/skills` | ANY / FA, SUP | Skills per operation |
| GET | `/assignments` | ANY | Filters: `station_id`, `worker_id`, `at` (timestamp), `active` |
| POST | `/assignments` | FA, SUP | Assign worker to station + operation |
| POST | `/assignments/bulk` | FA, SUP | Assign many workers at shift start |
| POST | `/assignments/{id}/end` | FA, SUP | End assignment |
| POST | `/attendance/import` | FA | CSV of card punches from an existing attendance system |

`POST /assignments`
```json
{ "worker_id": 120, "station_id": 41, "operation_id": 7,
  "valid_from": "2026-11-17T02:00:00Z", "valid_to": null }
```
Errors: `ASSIGNMENT_OVERLAP` (409), `WORKER_INACTIVE` (422).

---

## 8. Policies (versioned)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/policies` | ANY | Filters: `kind`, `scope_type`, `scope_id` |
| POST | `/policies` | FA | Create policy with first version |
| GET | `/policies/{id}` | ANY | Policy + active version |
| GET | `/policies/{id}/versions` | ANY | Version history |
| POST | `/policies/{id}/versions` | FA | New version (old one gets `effective_to`) |
| GET | `/policies/schema/{kind}` | ANY | JSON Schema for the policy body (the UI builds forms from it) |
| GET | `/policies/resolve?kind=shift&station_id=41&at=` | ANY | Which version applies here and now |

`kind`: `shift`, `target`, `thresholds`, `ranking`, `bonus`, `training`, `retention`.

`POST /policies/{id}/versions`
```json
{ "effective_from": "2026-12-01T00:00:00Z",
  "body": { "weights": { "production": 50, "quality": 35, "time": 15 },
            "min_coverage_pct": 80, "period": "month" } }
```
Errors: `POLICY_WEIGHTS_INVALID` (422), `POLICY_BODY_INVALID` (400 with field details).

---

## 9. Ingest (devices → central)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/ingest/events` | DEV | Batch of up to 500 events |
| POST | `/ingest/evidence/presign` | DEV | Get upload URLs for evidence images |
| POST | `/ingest/heartbeat` | DEV | Device heartbeat (batch) |
| GET | `/edge/config` | DEV | Station ↔ device mapping, zones, thresholds for this edge box |

`POST /ingest/events`
```json
{ "events": [
  { "event_uuid": "0f8c2b4e-6a1d-4c7e-9a52-1f3e8b7d2c10",
    "event_type": "worker_state", "state": "phone_use",
    "station_code": "L1-S07", "source_device_code": "EDGE1-CAM07",
    "start_time": "2026-11-17T09:12:03.120Z", "end_time": "2026-11-17T09:13:41.900Z",
    "confidence": 0.87, "model_version": "activity-v0.3.1",
    "evidence_keys": ["evidence/2026/11/17/0f8c.jpg"],
    "metadata": { "frames": 49 } }
] }
```
Response (per-row results; one bad row does not fail the batch):
```json
{ "accepted": 1, "duplicates": 0, "rejected": 0,
  "results": [ { "event_uuid": "0f8c...", "status": "accepted", "event_id": 991204 } ] }
```
Row errors: `DEVICE_STATION_MISMATCH`, `UNKNOWN_STATION`, `INVALID_EVENT_TYPE`, `TIME_IN_FUTURE`.

`event_type` / `state` values:
| event_type | state / payload |
|---|---|
| `worker_state` | `present`, `absent`, `working`, `idle`, `phone_use`, `uncertain` |
| `machine_state` | `running`, `stopped` (+ `metadata.current_a`) |
| `production_count` | `metadata.qty` |
| `needle_event` | `needle_break`, `suspected_break`, `thread_break`, `jam`, `other` |
| `quality_event` | `no_defect`, `possible_skipped_stitch`, `other_defect`, `unsuitable_image`, `needs_human` |
| `rfid_tap` | `metadata.card_id` |

---

## 10. Events and review

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/events` | SUP, FA, QM, MT, MG | Filters: `station_id`, `worker_id`, `line_id`, `event_type`, `state`, `review_status`, `source`, `from`, `to` |
| GET | `/events/{id}` | same | Detail + review history + evidence URLs (access audited) |
| GET | `/events/review-queue` | SUP, QM, MT | Pending events in caller's scope; filter `event_type` |
| POST | `/events/{id}/review` | SUP, QM, MT (by type) | Confirm / reject / reclassify |
| POST | `/events/manual` | SUP | Manually record an event (e.g. downtime reason, break) |
| GET | `/stations/{id}/timeline?date=` | ANY | Worker and machine state intervals for a shift date |

`POST /events/{id}/review`
```json
{ "decision": "reclassify", "new_state": "working",
  "reason_code_id": 14, "note": "Worker was checking the garment, not using a phone." }
```
Errors: `ALREADY_REVIEWED` (409; send `"override": true` with FA role to re-review).

---

## 11. Live stream (SSE)

`GET /stream/floor?factory_id=1&line_id=3` · ANY · `Content-Type: text/event-stream`

```
event: station_state
data: {"station_id":41,"worker_state":"working","machine_state":"running","worker_id":120,"ts":"..."}

event: alert
data: {"alert_id":5521,"type":"machine_stopped","severity":"warning","station_id":41}

event: alert_update
data: {"alert_id":5521,"status":"acknowledged"}
```
Heartbeat comment every 15 s. The client reconnects with `Last-Event-ID`.

---

## 12. Production

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/production-entries` | ANY | Filters: `worker_id`, `station_id`, `line_id`, `operation_id`, `status`, `from`, `to` |
| POST | `/production-entries` | SUP | Manual entry |
| PATCH | `/production-entries/{id}` | SUP | Edit while `draft` |
| POST | `/production-entries/{id}/confirm` | SUP | Confirm |
| POST | `/production-entries/import` | FA | CSV import from another system |
| GET | `/production/stats` | ANY | `group_by=hour\|shift\|day\|week` × `line\|station\|worker\|operation` |

`POST /production-entries`
```json
{ "worker_id": 120, "station_id": 41, "operation_id": 7,
  "period_start": "2026-11-17T03:00:00Z", "period_end": "2026-11-17T04:00:00Z",
  "qty_accepted": 58, "qty_rework": 3, "qty_rejected": 0 }
```

---

## 13. Quality

| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST | `/inspections` | ANY / QM | Inspection with defect lines |
| GET | `/inspections/{id}` | ANY | Detail |
| GET | `/quality/stats` | ANY | Defect rate, first-pass acceptance; `group_by=operation\|station\|machine\|worker\|defect_type` |

`POST /inspections`
```json
{ "station_id": 41, "worker_id": 120, "operation_id": 7,
  "inspected_at": "2026-11-17T05:10:00Z", "qty_checked": 50, "qty_passed": 47,
  "defects": [ { "defect_type_id": 2, "qty": 2 }, { "defect_type_id": 5, "qty": 1 } ] }
```

---

## 14. Needles

| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST / PATCH | `/needle-suppliers`, `/needle-models` | ANY / FA, MT | Lists |
| GET / POST | `/needle-batches` | ANY / FA, MT | Filters: `supplier_id`, `model_id`, `status` |
| GET / PATCH | `/needle-batches/{id}` | ANY / FA, MT | Detail incl. live stats |
| POST | `/needle-batches/import` | FA, MT | CSV import (see [IMPORT_TEMPLATES.md](IMPORT_TEMPLATES.md)) |
| POST | `/needle-batches/{id}/quarantine` | FA, QM, MT | Block new issues from this batch |
| POST | `/needle-batches/{id}/release` | FA, QM | Lift quarantine |
| GET / POST | `/needle-issues` | ANY / MT, SUP | Install needle on a machine (closes the open one) |
| POST | `/needle-issues/{id}/close` | MT, SUP | Remove: `removal_reason` |
| GET / POST | `/needle-events` | ANY / MT, SUP | Report a break manually |
| POST | `/needle-events/{id}/confirm` | MT | Confirm / reclassify type |
| GET | `/needles/stats` | ANY | `group_by=batch\|supplier\|model\|machine\|operation\|worker`, `from`, `to` |

`POST /needle-issues`
```json
{ "batch_id": 18, "machine_id": 77, "installed_at": "2026-11-17T06:02:00Z" }
```
Errors: `BATCH_QUARANTINED` (422), `BATCH_EXHAUSTED` (422).

`GET /needles/stats?group_by=batch` → data item:
```json
{ "batch_id": 18, "lot_no": "B-104", "supplier": "Supplier A",
  "issued": 20, "confirmed_breaks": 10, "operating_hours": 142.5,
  "break_rate_pct": 50.0, "breaks_per_1000h": 70.2, "breaks_per_10k_units": 12.4,
  "exposure_sufficient": true, "pattern": "batch" }
```

### Investigations
| Method | Path | Roles | Description |
|---|---|---|---|
| GET / POST | `/investigations` | ANY / FA, QM, MT | Filters: `subject_type`, `status` |
| GET / PATCH | `/investigations/{id}` | ANY / FA, QM, MT | Findings, action, outcome, close |
| POST | `/investigations/{id}/needle-events` | FA, QM, MT | Link events |

---

## 15. Analytics

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/overview` | ANY (scoped) | Admin dashboard data: per factory / line / station status, output vs target, downtime, open alerts, device health |
| GET | `/shift-summaries` | ANY | Filters: `worker_id`, `station_id`, `line_id`, `shift_date`, `from`, `to`, `is_stale` |
| GET | `/shift-summaries/{id}` | ANY | Detail with minute breakdown by state |
| POST | `/shift-summaries/recompute` | FA | Recompute for a date range / line (async, 202) |
| GET | `/machines/stats` | ANY | Run / stop / downtime by reason |
| GET | `/performance/snapshots` | MG, FA, SUP | Filters: `period`, `comparison_group`, `line_id` |
| GET | `/performance/snapshots/{id}/explain` | MG, FA, SUP | Score components, weights, raw inputs, policy version |

`GET /overview?factory_id=1` → data (shortened):
```json
{ "as_of": "2026-11-17T09:20:00Z",
  "totals": { "stations": 200, "active": 184, "machines_running": 171,
              "output_today": 9420, "target_today": 10400, "open_alerts": 12,
              "devices_offline": 3 },
  "lines": [ { "line_id": 3, "name": "Line 3", "stations": 40, "running": 36,
               "output": 1880, "target": 2080, "efficiency_pct": 71.4,
               "open_alerts": { "critical": 1, "warning": 3 } } ] }
```

---

## 16. Bonus and training

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/bonus-records` | MG, FA | Filters: `period`, `status` |
| POST | `/bonus-records/{id}/decide` | MG | `{ "decision": "approved" \| "rejected", "note": "" }` |
| GET | `/training-records` | MG, FA, SUP | Filters: `status`, `worker_id`, `operation_id` |
| PATCH | `/training-records/{id}` | SUP, MG | Move status, set trainer, date, follow-up, result |

Both are off until the `bonus` / `training` policy is enabled.

---

## 17. Alerts and notifications

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/alerts` | ANY (scoped) | Alert center. Filters: `factory_id`, `line_id`, `station_id`, `type`, `severity`, `status`, `from`, `to` |
| GET | `/alerts/summary` | ANY | Counts by severity / status / type (for dashboard badges) |
| GET | `/alerts/{id}` | ANY | Detail with linked event / machine / batch / worker |
| POST | `/alerts/{id}/ack` | ANY with access | Acknowledge |
| POST | `/alerts/{id}/resolve` | ANY with access | Resolve with note |
| GET | `/alert-rules` | FA, SA | List rules |
| POST | `/alert-rules` | FA | Create rule |
| PATCH | `/alert-rules/{id}` | FA | Edit / enable / disable |
| GET | `/alert-rules/sources` | FA | Event types and metrics a rule can use (the UI builds the rule form from this) |
| POST | `/alert-rules/{id}/test` | FA | Dry-run against the last 7 days; returns how many alerts it would have fired |
| GET | `/notifications` | ANY | Own notifications; `unread=true` |
| POST | `/notifications/read` | ANY | `{ "ids": [..] }` or `{ "all": true }` |

`POST /alert-rules`
```json
{ "name": "Long machine stop", "factory_id": 1,
  "source": { "event_type": "machine_state", "state": "stopped" },
  "condition": { "min_duration_sec": 600 },
  "severity": "warning", "recipient_roles": ["supervisor", "maintenance"],
  "scope_type": "line", "scope_id": 3, "is_enabled": true }
```
Metric-based rule:
```json
{ "name": "Batch break rate", "factory_id": 1,
  "source": { "metric": "needle_batch.break_rate_pct" },
  "condition": { "operator": ">", "threshold": 15, "min_exposure": { "issued": 10, "operating_hours": 50 } },
  "severity": "critical", "recipient_roles": ["quality", "factory_admin"],
  "scope_type": "factory", "scope_id": 1, "is_enabled": true }
```

---

## 18. Reports

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/reports/types` | ANY | Available report types and their parameters |
| POST | `/reports` | ANY (scoped) | Start report (202) |
| GET | `/reports/{id}` | owner | Status + signed download URL when ready |

```json
// POST /reports
{ "type": "shift_report", "format": "pdf", "locale": "bn",
  "params": { "line_id": 3, "shift_date": "2026-11-17" } }
// 202 data
{ "report_id": 311, "status": "queued" }
```
Types: `shift_report`, `daily_line_report`, `worker_period_report`, `needle_batch_report`, `quality_report`, `downtime_report`. Formats: `pdf`, `csv`.

---

## 19. Audit and ops

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/audit-logs` | SA, FA | Filters: `actor_user_id`, `entity`, `entity_id`, `action`, `from`, `to` |
| GET | `/healthz` | public | Process alive |
| GET | `/readyz` | public | DB, Redis, MinIO reachable |
| GET | `/metrics` | internal network only | Prometheus metrics |

---

## 20. Error code catalog

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Field errors in `details.fields` |
| `UNAUTHENTICATED` | 401 | No or expired session / token |
| `INVALID_CREDENTIALS` | 401 | Wrong login |
| `ACCOUNT_LOCKED` | 403 | Too many failed logins |
| `FORBIDDEN` | 403 | Role not allowed |
| `CSRF_FAILED` | 403 | Missing / wrong CSRF token |
| `NOT_FOUND` | 404 | Missing or out of scope |
| `VERSION_CONFLICT` | 409 | Stale `If-Match` |
| `IN_USE` | 409 | Cannot delete; deactivate instead |
| `ASSIGNMENT_OVERLAP` | 409 | Time range overlaps another assignment |
| `ALREADY_REVIEWED` | 409 | Event already reviewed |
| `POLICY_WEIGHTS_INVALID` | 422 | Weights do not total 100 |
| `POLICY_BODY_INVALID` | 400 | Body fails the policy schema |
| `WORKER_INACTIVE` | 422 | Worker deactivated |
| `BATCH_QUARANTINED` | 422 | Batch blocked |
| `BATCH_EXHAUSTED` | 422 | All needles in the batch already issued |
| `DEVICE_UNKNOWN` | 401 | Device token not recognized |
| `DEVICE_STATION_MISMATCH` | row | Device not mapped to that station |
| `UNKNOWN_STATION` | row | Station code not found |
| `INVALID_EVENT_TYPE` | row | Unsupported event type / state |
| `TIME_IN_FUTURE` | row | Event more than 24 h ahead |
| `RATE_LIMITED` | 429 | Slow down |
| `INTERNAL_ERROR` | 500 | Unexpected; see `request_id` in logs |
