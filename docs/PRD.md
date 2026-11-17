# Product Requirements Document (PRD)

**Product:** StitchSense (working name — check trademark availability before public use)
**Source:** [PROJECT_DOCUMENTATION.md](../PROJECT_DOCUMENTATION.md) (concept spec)
**Status:** Draft v1 — 2026-11-17
**Related:** [TRD](TRD.md) · [Flows](FLOWS.md) · [Backend Design](BACKEND_DESIGN.md) · [Deployment Requirements](DEPLOYMENT_REQUIREMENTS.md)

---

## 1. Product summary

A monitoring and analytics platform for the sewing floor of garment / textile factories. It combines camera-based computer vision, machine sensors, production records and admin-defined policies to show, per sewing station:

- how scheduled time is spent (productive, idle, break, downtime, probable phone use, uncertain),
- how many accepted units are produced against target,
- quality events (skipped stitch, other seam defects),
- needle breaks traced to supplier, batch, machine, operation and worker,
- fair, operation-normalized performance, bonus eligibility and training recommendations.

The platform **supports** management decisions. It never makes automatic disciplinary, bonus or training decisions. Every AI detection carries a confidence value and can be reviewed and corrected by a human.

## 2. Business model and delivery

- Sold to multiple factories. **Each client gets its own isolated installation** (own server, own database, own data). There is no shared multi-tenant cloud.
- Deployment is **hybrid**: an edge box on the factory floor processes video locally; a central app server (client on-prem server or client-owned cloud VPS) hosts the API, database and dashboards. Raw video never leaves the factory.
- One installation can hold several factories / floors / lines of the same client company.
- What each client must provide is listed in [DEPLOYMENT_REQUIREMENTS.md](DEPLOYMENT_REQUIREMENTS.md).

## 3. Goals and non-goals

### Goals
1. Accurate, explainable working-time accounting per worker, per shift, against configurable policy.
2. Confirmed production counts and SMV-based efficiency per operation.
3. Needle-break traceability to batch / machine / operation / worker, with fair exposure-based rates.
4. Quality event capture and review.
5. Fully configurable policies (shifts, breaks, targets, ranking weights, thresholds) — no hard-coded factory rules.
6. Human review loop for every uncertain or consequential output.
7. **Everything dynamic.** Nothing about a factory is hard-coded: number of factories, floors, lines and stations (10, 100, 200 or more), machine brands and types, shifts, targets, thresholds, defect types, reason codes, alert rules and labels are all created and edited by admins in the UI and stored in the database. The software has no fixed station limit; only hardware sizing grows with scale.
8. **Brand-agnostic.** Works with any sewing-machine brand or model. Machine state comes from a clamp-on current sensor that fits any machine; brand-specific machine signals are optional extras.

### Non-goals (MVP)
- Facial recognition or biometric identification of workers.
- Audio recording.
- Automatic payroll, bonus payment or disciplinary action.
- Worker self-service login (workers are records, not users — see §5).
- Shared multi-tenant SaaS hosting.

## 4. Release plan

| Release | Content | Evidence source |
|---|---|---|
| **R1 — Platform MVP** | Auth/RBAC, factory structure, workers, machines, assignments, shift/break policies, operations + SMV, manual production entry, event ingestion API, event simulator, review queue, time accounting, dashboards (admin, supervisor), admin alert center + configurable alert rules, CSV imports, reports, audit log, English + Bangla UI (tasks: [TASKS_R1.md](TASKS_R1.md)) | Manual entry + simulator |
| **R2 — Machine signals** | Machine running/stopped via current sensor (ESP32 + CT clamp), downtime reasons, device health, needle inventory & needle-break logging (sensor or supervisor-confirmed), needle analytics | Sensors + manual |
| **R3 — Vision pilot** | Edge service: worker presence/activity, probable phone use, idle fusion (camera + machine + schedule), evidence snapshots | Camera + sensors |
| **R4 — Quality & analytics** | Close-up seam inspection prototype (skipped stitch), quality dashboard, performance scoring, ranking, bonus eligibility list, training recommendations | All sources |

Bonus and training recommendations stay **disabled by default** until the client validates data quality (source spec §22 phase 4).

Testing runs on two tracks in parallel: **simulated data** (seed + event simulator, for development and demos) and **real-factory pilot** (a few stations, observation mode first).

## 5. Users and roles

Only staff log in. Workers are stored as records and identified by employee ID (and optional RFID card).

| Role | Main jobs |
|---|---|
| **System Admin** | Install-level settings, users, roles, devices, data retention, backups |
| **Factory Admin** | Factory structure, policies (shift, break, targets, ranking, alerts), suppliers, operations |
| **Supervisor** | Live floor view, assign workers to stations, review activity / phone-use / idle events, confirm production, add downtime reasons |
| **Quality Manager** | Review quality events, record inspection results, defect trends |
| **Maintenance** | Machine events, needle breaks, needle replacement, investigations |
| **Management (read-only)** | Reports, rankings, bonus / training recommendations, approve or reject them |

A user can hold several roles. Access can be scoped to a factory or line.

## 6. Functional requirements

Priority: **M** = must (R1/R2), **S** = should (R3/R4), **C** = could (later).

### 6.1 Access and landing
| ID | Requirement | P |
|---|---|---|
| F-ACC-1 | Public landing page: intro, capabilities, workflow, benefits, contact, login link | M |
| F-ACC-2 | Email/username + password login, password reset by admin, session timeout | M |
| F-ACC-3 | Role-based access, scoped to factory/line | M |
| F-ACC-4 | UI in English and Bangla, switchable per user | M |

### 6.2 Factory structure and master data
| ID | Requirement | P |
|---|---|---|
| F-ORG-1 | CRUD for factory → floor → line → station | M |
| F-ORG-2 | Machines with type, brand, model, serial; machines are assigned to stations **with time ranges** (machines get swapped) | M |
| F-ORG-3 | Workers: employee ID, name, skills/operations, optional RFID card ID, active flag | M |
| F-ORG-4 | Worker-to-station assignments with start/end time; history is never overwritten | M |
| F-ORG-5 | Products, operations, and **SMV (Standard Minute Value)** per operation; counting-unit definition per operation | M |
| F-ORG-6 | Devices (cameras, sensors, edge boxes) mapped to stations, with heartbeat status | M |
| F-ORG-7 | CSV import for workers, machines, stations | S |

### 6.3 Policies (dynamic configuration)
| ID | Requirement | P |
|---|---|---|
| F-POL-1 | Shift policies: start, end, cross-midnight support, break windows, overtime rules, daily/weekly limits | M |
| F-POL-2 | Production targets per operation / line / shift | M |
| F-POL-3 | Idle threshold, phone-use min duration + confidence threshold, alert thresholds | M |
| F-POL-4 | Ranking weights (must total 100%), eligibility rules, minimum data coverage | S |
| F-POL-5 | Training and bonus rules | S |
| F-POL-6 | **Policies are versioned.** Any stored calculation records which policy version it used. Old versions are kept, not edited | M |
| F-POL-7 | Every config change is written to the audit log (who, when, old value, new value) | M |
| F-POL-8 | All lists and values shown in the UI (machine types, brands, defect types, reason codes, alert rules, roles' scopes, thresholds) come from admin-editable data, with no hard-coded values in code. Each list supports add / edit / deactivate | M |

### 6.4 Shift and time accounting
| ID | Requirement | P |
|---|---|---|
| F-TIME-1 | Shift record per worker per shift date (shift date = date the shift **started**) | M |
| F-TIME-2 | Worker state timeline built from events using the precedence rule in §7.1; no minute counted twice | M |
| F-TIME-3 | Machine state is a **separate timeline** from worker state | M |
| F-TIME-4 | Per shift: scheduled work time, productive, idle, phone-use, downtime, setup/material delay, break, uncertain, overtime | M |
| F-TIME-5 | Show data coverage % (time with valid device data / scheduled time) | M |
| F-TIME-6 | Supervisor can add reason codes for pauses (material wait, setup, quality check, etc.) | M |

### 6.5 Event ingestion and review
| ID | Requirement | P |
|---|---|---|
| F-EVT-1 | One ingestion API for all sources (simulator, manual, sensor, edge vision) using the common event schema | M |
| F-EVT-2 | Every event stores source device, model/sensor version, confidence, review status | M |
| F-EVT-3 | Review queue: confirm / reject / reclassify; corrections are stored as new review records, raw event is never modified | M |
| F-EVT-4 | Events below confidence threshold are shown as "uncertain", not as fact | M |
| F-EVT-5 | Idempotent ingestion (edge retries must not duplicate events) | M |
| F-EVT-6 | Event simulator that generates realistic station events for demo and testing | M |

### 6.6 Production
| ID | Requirement | P |
|---|---|---|
| F-PRD-1 | Manual / supervisor production entry per worker, operation, hour or shift | M |
| F-PRD-2 | Detected counts (sensor / vision) kept separate from confirmed counts | M |
| F-PRD-3 | Metrics: confirmed accepted units, rejected/rework, units per productive hour, target %, **efficiency % = (units × SMV) / minutes worked × 100** | M |
| F-PRD-4 | Hourly / shift / day / week trends | M |
| F-PRD-5 | Import counts from client production system (CSV / API) | C |

### 6.7 Machine and downtime
| ID | Requirement | P |
|---|---|---|
| F-MCH-1 | Machine running / stopped from sensor, with stop duration | M (R2) |
| F-MCH-2 | Downtime reason codes (breakdown, needle change, thread change, no material, setup) | M |
| F-MCH-3 | Alert when stop exceeds threshold | M |

### 6.8 Needles
| ID | Requirement | P |
|---|---|---|
| F-NDL-1 | Suppliers, needle models (type, size), batches (lot no., received date, qty received) | M |
| F-NDL-2 | Needle issue log: which batch was installed on which machine/station, when, by whom; replacement closes the previous issue | M |
| F-NDL-3 | Needle events: confirmed break, suspected break, thread break, machine jam, other, unknown — each linked to the **specific needle issue** | M |
| F-NDL-4 | Rates: breaks / needles issued, breaks per 1,000 operating hours, breaks per 10,000 units — by batch, supplier, machine, operation, worker | M |
| F-NDL-5 | Threshold alerts for batch / machine / worker patterns, with an investigation record (findings, action, outcome) | M |
| F-NDL-6 | Batch quarantine flag | S |

### 6.9 Activity vision (R3)
| ID | Requirement | P |
|---|---|---|
| F-VIS-1 | Worker present / absent at station | S |
| F-VIS-2 | Working vs not-working activity estimate | S |
| F-VIS-3 | Probable phone-use event with confidence, min duration, evidence snapshot (blurred faces optional) | S |
| F-VIS-4 | Idle event = fusion of camera + machine + schedule + production events, after configurable threshold | S |

### 6.10 Quality (R4)
| ID | Requirement | P |
|---|---|---|
| F-QLT-1 | Manual quality inspection entry (defect type, qty, station, operation) | M |
| F-QLT-2 | Defect type catalogue (skipped stitch, puckering, open seam, etc.) | M |
| F-QLT-3 | Close-up seam inspection model: outputs no-defect / possible skipped stitch / other defect / image unsuitable / needs human | S |
| F-QLT-4 | Quality dashboard: defect rate by operation/station/machine/worker, first-pass acceptance | S |

### 6.11 Performance, bonus, training (R4)
| ID | Requirement | P |
|---|---|---|
| F-PERF-1 | Periodic performance snapshots per worker using active ranking policy version | S |
| F-PERF-2 | Rankings only among workers on comparable operations, or normalized by SMV | S |
| F-PERF-3 | Workers below minimum data coverage are excluded and marked "insufficient data" | S |
| F-PERF-4 | Score explanation: each component, weight, and source data | S |
| F-PERF-5 | Bonus eligibility list → management approves / rejects | S |
| F-PERF-6 | Training recommendation → supervisor checks external causes (machine, batch, material) → approve / close → follow-up evaluation | S |

### 6.12 Alerts, reports, audit
| ID | Requirement | P |
|---|---|---|
| F-ALR-1 | Alert types per source spec §19, with severity, station, confidence, review status | M |
| F-ALR-2 | **Alert center on the admin dashboard**: all open and past alerts across the whole installation, with live updates, filters (factory, line, station, type, severity, status, date), acknowledge / resolve, and a link to the related event, machine, batch or worker | M |
| F-ALR-3 | **Alert rules are configurable** in the UI: enable / disable, trigger condition and threshold, minimum duration, severity, which roles see it, and the lines it applies to. Admins can create new rules from the available event types and metrics | M |
| F-ALR-4 | Notification bell for every logged-in user, showing alerts for their role and lines | M |
| F-ALR-5 | Email, SMS or WhatsApp delivery | C |
| F-ADM-1 | **Admin overview dashboard**: live summary of every factory, line and station (status, output vs target, downtime, open alerts, device health). Every widget is driven by live data and current config, with no fixed layout per factory size | M |
| F-RPT-1 | Shift report, daily line report, needle batch report, worker period report; export CSV and PDF | M |
| F-AUD-1 | Audit log for logins, config changes, reviews/corrections, approvals, evidence access | M |

## 7. Key business rules

### 7.1 Worker-state precedence (no double counting)
For each minute of a worker's shift, exactly one worker state applies, chosen by this order:

1. **Break** (scheduled or authorized)
2. **Machine downtime** (machine stopped with a downtime reason)
3. **Material / setup delay** (supervisor reason code)
4. **Phone use** (confirmed, or probable above threshold)
5. **Productive**
6. **Idle** (after threshold)
7. **Uncertain** (no reliable data)

`Scheduled Work Time + Overtime = sum of all non-break states`. Coverage gaps count as Uncertain.

### 7.2 Worker attribution
No face recognition. The worker at a station is known from:
1. the active worker assignment (set by supervisor), optionally confirmed by
2. a card tap at the station at shift start (R2+). Many factories already issue RFID / ID cards for attendance, so the same card number is stored on the worker record and reused. A low-cost reader at the station reads it. If the factory's attendance system can export punches (CSV or API), those can be imported as well. Card use is a per-factory setting.

If neither exists, events are stored against the station only and marked "unattributed".

### 7.3 Fairness rules
- A needle break is never attributed to worker technique until batch, machine and operation patterns have been checked.
- Phone-use and idle are indicators that need review, never the only basis for a score.
- Scores are computed only from confirmed or reviewed data where the policy requires it.

## 8. Success metrics (per client pilot)

| Metric | Target (initial, to be agreed with client) |
|---|---|
| Production count error vs manual count | ≤ 3% |
| Machine running/stopped accuracy | ≥ 98% |
| Phone-use event precision | ≥ 90% (recall reported, not gated) |
| Activity state accuracy vs reviewed samples | ≥ 85% |
| Device uptime during shift | ≥ 97% |
| Event review backlog | Cleared within 24 h |
| Supervisor time on review | ≤ 20 min / shift |

## 9. Privacy and responsible use (product requirements)

- Workers are informed in writing of what is monitored and why; client signs off before go-live.
- No audio, no facial recognition, camera zones limited to the work area.
- Store event metadata by default; store only short evidence snapshots/clips for flagged events. Default retention: evidence 30 days, events 2 years (configurable).
- Faces in evidence images can be blurred at the edge (configurable).
- Workers can dispute an event through their supervisor; disputes are recorded.
- Human approval is required for every bonus, training and HR-relevant output.

## 10. Corrections to the source concept document

Issues found in [PROJECT_DOCUMENTATION.md](../PROJECT_DOCUMENTATION.md), and how this PRD resolves them:

| # | Source section | Issue | Resolution |
|---|---|---|---|
| 1 | §16 ER | `STATION ||--|| MACHINE` fixes one machine per station forever; machines are swapped for repair | Time-bound `machine_assignments` |
| 2 | §16 ER | `NEEDLE_EVENT` links only to batch, so station/machine/worker at break time is lost | Needle events link to the specific `needle_issue` |
| 3 | §10.2 vs §10.4 | Example uses needles **received** (20); formula uses needles **issued** | Use **issued**; unused needles cannot break |
| 4 | §16 tables | `admin_users` — but supervisors, quality and maintenance also log in | `users` + `roles` + `user_roles` |
| 5 | §6.1–6.2 | "Machine running" is listed as a worker activity state; no rule for overlaps; overtime missing from the formula | Separate worker / machine timelines, precedence rule §7.1, overtime included |
| 6 | §6.2 | Night shifts crossing midnight not handled | Shift date = start date; policies support cross-midnight |
| 7 | §11 | "Standard operation time" mentioned but not used in formulas | SMV-based efficiency (industry standard) |
| 8 | — | How the system knows *which worker* is at a station is not defined | Assignment + optional RFID tap (§7.2) |
| 9 | §16 | Missing entities: operations/products, targets, policy versions, alerts, investigations, defect types, event reviews, device heartbeats | Added in [BACKEND_DESIGN.md](BACKEND_DESIGN.md) |
| 10 | §20 | Retention periods not given | Defaults in §9, configurable |

## 11. Decisions on earlier open questions

| Question | Decision |
|---|---|
| Product name | **StitchSense** (working name; can change later) |
| Machine brands | Any brand, mixed per factory; brand / model / type are admin-managed lists |
| Number of stations | Unknown and different for every factory; fully configurable, no software limit |
| ERP / production system | Not required. Optional CSV import in R1; per-client API connector only if a client asks |
| Worker card tap | Supported and optional per factory; reuse existing attendance cards where they exist |
| Alert channels | In-app: admin alert center + notification bell. Email / SMS later |

## 12. Remaining open questions

1. Is face-blur on evidence images on by default? (Proposed: on.)
2. Which factory will be the first real pilot? Its machine models decide whether brand-specific needle-break signals are available.
