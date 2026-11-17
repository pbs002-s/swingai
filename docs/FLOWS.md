# User and System Flows

**Status:** Draft v1 — 2026-11-17
**Related:** [PRD](PRD.md) · [TRD](TRD.md) · [Backend Design](BACKEND_DESIGN.md)

Screens for each flow will be mapped once the UI design is uploaded.

---

## 1. App navigation (by role)

```mermaid
flowchart TD
    L["Landing page"] --> LOGIN["Login"]
    LOGIN --> HOME{"Role home"}
    HOME -->|Admin| A["Admin: Overview"]
    HOME -->|Supervisor| S["Supervisor: Live floor"]
    HOME -->|Quality| Q["Quality: Defects"]
    HOME -->|Maintenance| M["Maintenance: Machines & needles"]
    HOME -->|Management| P["Performance & approvals"]

    A --> A1["Factory structure"]
    A --> A2["Workers / machines / devices"]
    A --> A3["Policies (shift, targets, ranking, alerts)"]
    A --> A4["Users & roles"]
    A --> A5["Audit log"]

    S --> S1["Station detail + timeline"]
    S --> S2["Review queue"]
    S --> S3["Assignments"]
    S --> S4["Production entry"]
    S --> S5["Shift report"]

    M --> M1["Needle inventory & issue"]
    M --> M2["Needle events & investigations"]
    M --> M3["Machine downtime"]

    Q --> Q1["Inspection entry"]
    Q --> Q2["Quality event review"]

    P --> P1["Rankings + score explanation"]
    P --> P2["Bonus approvals"]
    P --> P3["Training recommendations"]
```

## 2. New client onboarding (install → go-live)

```mermaid
flowchart TD
    A["Site survey<br/>(machines, layout, network, policies)"] --> B["Client prepares hardware<br/>(see Deployment Requirements)"]
    B --> C["Install central stack<br/>docker compose up"]
    C --> D["Create System Admin, factory, time zone"]
    D --> E["Import stations, machines, workers (CSV)"]
    E --> F["Define products, operations, SMV, targets"]
    F --> G["Create shift & break policies"]
    G --> H["Register edge box + devices, issue device tokens"]
    H --> I["Map devices to stations, draw camera zones"]
    I --> J["Worker notice signed / privacy sign-off"]
    J --> K["Observation mode (2–4 weeks)<br/>compare with manual records"]
    K --> L{"Acceptance criteria met?"}
    L -->|No| M["Tune thresholds / camera / sensors"] --> K
    L -->|Yes| N["Go live; enable scoring features stepwise"]
```

## 3. Daily shift flow (supervisor)

```mermaid
sequenceDiagram
    participant SUP as Supervisor
    participant APP as Web app
    participant API as Backend
    participant EDGE as Edge
    participant W as Worker (at station)

    SUP->>APP: Open live floor (shift start)
    APP->>API: Get stations + today's assignments
    SUP->>APP: Confirm / change worker assignments
    APP->>API: POST assignments (time-bound)
    W->>EDGE: RFID tap (optional)
    EDGE->>API: rfid_tap event → matches assignment
    loop During shift
        EDGE->>API: machine_state / worker_state events
        API-->>APP: SSE station updates + alerts
        SUP->>APP: Add pause reason (material wait, setup)
        SUP->>APP: Enter hourly production
    end
    SUP->>APP: Clear review queue
    API->>API: Shift close job → shift summaries
    SUP->>APP: View / export shift report
```

## 4. Event ingestion pipeline (system)

```mermaid
flowchart TD
    A["Sensor / camera / simulator / manual"] --> B["Edge collector writes to SQLite outbox"]
    B --> C["POST /ingest/events (batch, device token)"]
    C --> D{"Valid schema + known device?"}
    D -->|No| E["Reject row, log error, report to edge"]
    D -->|Yes| F{"event_uuid already stored?"}
    F -->|Yes| G["Ack as duplicate"]
    F -->|No| H["Resolve station → machine, worker, policy version<br/>(time-bound lookups)"]
    H --> I["Insert raw event (append-only)"]
    I --> J{"Confidence ≥ threshold?"}
    J -->|No| K["review_status = pending (uncertain)"]
    J -->|Yes| L["review_status = auto_accepted<br/>(or pending if type requires review)"]
    K --> M["Publish to Redis → SSE"]
    L --> M
    M --> N["Alert rules evaluated"]
    I --> O["Worker: sessionize into timelines"]
```

Phone-use events, needle events and quality defects always start as `pending` regardless of confidence (PRD §7.3).

## 5. Event review flow

```mermaid
flowchart TD
    A["Review queue (filtered by my lines)"] --> B["Open event: timeline, evidence snapshot, confidence, machine state"]
    B --> C{"Decision"}
    C -->|Confirm| D["review: confirmed"]
    C -->|Reject| E["review: rejected + reason"]
    C -->|Reclassify| F["review: reclassified to new type/state"]
    D --> G["Insert event_reviews row (raw event untouched)"]
    E --> G
    F --> G
    G --> H["Recompute affected shift summary"]
    G --> I["Audit log entry"]
```

## 6. Time accounting (shift close job)

```mermaid
flowchart TD
    A["Shift end + grace period (e.g. 30 min)"] --> B["Load shift policy version + breaks"]
    B --> C["Load worker_state, machine_state, downtime reasons, reviews"]
    C --> D["Build minute grid for the shift"]
    D --> E["Apply precedence:<br/>Break > Downtime > Setup/Material > Phone > Productive > Idle > Uncertain"]
    E --> F["Sum minutes per state; compute overtime"]
    F --> G["Compute coverage % and production metrics (units, target %, SMV efficiency)"]
    G --> H["Upsert shift_summary (with policy_version_id, computed_at)"]
    H --> I["Late events or reviews → mark summary stale → recompute"]
```

## 7. Needle lifecycle and break investigation

```mermaid
flowchart TD
    A["Batch received: supplier, model, lot, qty"] --> B["Needle issued to machine (needle_issue opened)"]
    B --> C{"Event"}
    C -->|Routine replacement| D["Close issue: reason = replaced"]
    C -->|Sensor alarm / supervisor report| E["needle_event (pending), linked to open needle_issue"]
    E --> F["Maintenance confirms type:<br/>needle break / suspected / thread break / jam / other"]
    F --> G["Close issue: reason = broken; open new issue for replacement"]
    G --> H["Nightly aggregation: rates per batch, supplier, machine, operation, worker<br/>(per needles issued, per 1,000 h, per 10,000 units)"]
    H --> I{"Above threshold with minimum exposure?"}
    I -->|Batch pattern| J["Alert quality/procurement → investigation"]
    I -->|Machine pattern| K["Alert maintenance → investigation"]
    I -->|Worker pattern, other causes ruled out| L["Coaching suggestion → supervisor"]
    I -->|No| M["Continue monitoring"]
    J --> N["Record findings, action (quarantine / service / coach), outcome"]
    K --> N
    L --> N
```

## 8. Performance, bonus and training (period end)

```mermaid
flowchart TD
    A["Period end (week / month)"] --> B["Collect shift summaries + confirmed production + quality"]
    B --> C{"Coverage ≥ policy minimum?"}
    C -->|No| D["Mark 'insufficient data', exclude"]
    C -->|Yes| E["Normalize by SMV / comparable operation group"]
    E --> F["Apply ranking policy version (weights)"]
    F --> G["Store performance_snapshot + score breakdown"]
    G --> H["Bonus rules → eligibility list"]
    G --> I["Training rules → recommendations"]
    H --> J["Management approves / rejects (audited)"]
    I --> K["Supervisor checks machine / batch / material causes"]
    K -->|External cause| L["Close + link investigation"]
    K -->|Skill gap| M["Approve training → schedule → follow-up evaluation"]
```

## 9. Policy change flow

```mermaid
flowchart TD
    A["Admin edits a policy"] --> B["Validation (e.g. weights = 100%, break inside shift)"]
    B --> C["Create new policy version with effective_from"]
    C --> D["Previous version gets effective_to"]
    D --> E["Audit log: old vs new"]
    E --> F["New calculations use the version active at event time;<br/>historical summaries keep their original version"]
```

## 10. Device health

```mermaid
flowchart TD
    A["Device heartbeat every 30 s"] --> B["Redis: last_seen per device"]
    B --> C["Watchdog every 60 s"]
    C --> D{"Missed > 3 min during shift?"}
    D -->|Yes| E["Device offline alert → technical admin;<br/>affected station time → Uncertain"]
    D -->|No| F["OK"]
    E --> G["Device back → alert auto-resolves"]
```
