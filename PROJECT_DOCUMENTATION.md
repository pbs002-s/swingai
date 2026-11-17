# AI-Powered Smart Textile Factory Monitoring & Workforce Intelligence System

> **Project Documentation --- Concept, Requirements, Architecture,
> Analytics, and Development Roadmap**\
> **Status:** Initial project specification\
> **Domain:** Textile / Garment Manufacturing --- Sewing Floor\
> **Primary users:** Factory administrators, production supervisors,
> quality managers, maintenance teams, and workers

------------------------------------------------------------------------

## 1. Executive Summary

The proposed system is an AI-powered monitoring and analytics platform
for the sewing-floor operations of a textile or garment factory.

In the target environment, each sewing station generally has one sewing
machine and one assigned worker. A worker may have a shift of
approximately eight hours, including a break such as a one-hour lunch
period. Actual working hours, break policies, shift lengths, and
production targets vary by factory and must therefore be configurable by
an administrator.

The system will combine camera-based computer vision, machine-level
signals or sensors, production records, and administrative configuration
to understand what happens at each sewing station.

It aims to:

-   Measure productive working time and identify idle time.
-   Detect defined activities such as mobile-phone use during working
    periods.
-   Estimate or count completed production output.
-   Identify possible skipped-stitch events and other visible
    sewing-quality issues.
-   Detect and record needle-break events using a suitable sensing
    method.
-   Compare needle-break patterns by supplier, product, batch, machine,
    and worker.
-   Calculate fair worker-performance scores and rankings.
-   Recommend coaching or training when performance or quality
    indicators show a need.
-   Support transparent, configurable bonus and training policies.

The system is intended to support management decisions, not to make
automatic disciplinary decisions. AI findings should be reviewable, and
uncertain detections should be marked as uncertain rather than treated
as facts.

------------------------------------------------------------------------

## 2. Problem Statement

Sewing-floor managers often need to understand several operational
questions:

1.  Is a worker actively performing the assigned sewing operation during
    scheduled working time?
2.  How much time is productive, idle, or spent on a defined non-work
    activity?
3.  How many acceptable products or operation units has the worker
    completed?
4.  Is the sewing machine running while the required sewing operation is
    not being completed?
5.  Are skipped stitches or other quality defects occurring?
6.  How often does a sewing needle break?
7.  Are needle breaks associated with a particular supplier or needle
    batch, a particular machine, a particular operation, or a particular
    worker?
8.  Which workers are performing well under comparable conditions?
9.  Which workers may benefit from additional training?
10. Can factory-specific shift limits, breaks, targets, and policies be
    configured without changing the software?

A useful solution must connect worker activity, machine activity,
production output, quality, and consumable-material information. Looking
at only one metric can lead to incorrect conclusions. For example, a low
production count may be caused by difficult work, machine downtime,
material problems, poor needle quality, or a worker's training needs.

------------------------------------------------------------------------

## 3. Project Objectives

### 3.1 Primary objectives

-   Build a centralized monitoring platform for sewing stations.
-   Measure working, idle, and break time against configurable
    schedules.
-   Detect selected worker activities using computer vision.
-   Measure production output using a verified counting method.
-   detect or infer machine and sewing-quality events using appropriate
    sensors and vision.
-   Maintain needle-break records and traceability to needle batches.
-   Generate worker, machine, production, and needle-quality analytics.
-   Support configurable performance ranking and training
    recommendations.
-   Give administrators control over factory policies and system
    configuration.

### 3.2 Expected outcomes

-   Better visibility into sewing-floor operations.
-   More consistent production reporting.
-   Earlier identification of quality and equipment issues.
-   Evidence-based worker coaching and training decisions.
-   Better supplier and needle-batch quality tracking.
-   More transparent performance and bonus evaluation.

------------------------------------------------------------------------

## 4. Operating Environment and Assumptions

The following are initial assumptions from the project discussion. They
must be confirmed with the factory before implementation.

  -----------------------------------------------------------------------
  Item                    Initial understanding   Configuration /
                                                  validation
  ----------------------- ----------------------- -----------------------
  Work area               Textile / garment       Confirm factory layout
                          sewing floor            

  Sewing station          Generally one machine   Support different
                          and one worker          arrangements

  Example shift           8 hours                 Admin-configurable

  Example break           1 hour, such as lunch   Admin-configurable

  Example scheduled work  7 hours after a 1-hour  Calculated from actual
  time                    break                   policy

  Worker assignment       Worker assigned to a    Support reassignment
                          sewing station          and shared stations if
                                                  needed

  Monitoring              Camera / computer       Camera placement and
                          vision                  policy approval
                                                  required

  Needle movement         Very fast and needle is Sensor-based detection
                          small                   likely required

  Production              Count completed         Define what counts as
                          products or operation   one unit
                          units                   

  Performance policy      Ranking, bonus, and     Admin-configurable and
                          training                reviewable
                          recommendations         
  -----------------------------------------------------------------------

**Important:** The eight-hour shift and one-hour break are examples, not
fixed system constants. The application must support different shift
lengths, break arrangements, overtime rules, and working-hour limits.

------------------------------------------------------------------------

## 5. Scope and Core Modules

### 5.1 Landing Page and Application Access

The public or internal landing page should explain the platform and
provide secure access to the application.

Suggested sections:

-   Project introduction
-   Key capabilities
-   How the monitoring workflow operates
-   Benefits for production and quality management
-   Login / authorized access
-   Contact or support information

### 5.2 Admin and Factory Configuration

Administrators should be able to configure the system for each factory
or production line.

Configurable items should include:

-   Factory, building, floor, line, and station structure
-   Machines and machine types
-   Worker profiles and assignments
-   Shift start and end times
-   Break duration and break windows
-   Daily and weekly working-hour limits
-   Overtime rules
-   Production targets
-   Product / operation types and standard operation times
-   Ranking weights and eligibility rules
-   Training thresholds and review rules
-   Bonus rules
-   Needle suppliers, models, and batch identifiers
-   Camera and sensor mappings
-   Alert thresholds and notification recipients
-   Data-retention and access policies

Configuration changes should be logged with the administrator,
timestamp, and previous/new values.

### 5.3 Worker and Station Management

Each worker and station should have a unique identifier.

A station record may include:

-   Station ID
-   Factory / floor / line
-   Sewing machine ID
-   Camera ID
-   Sensor IDs
-   Current worker assignment
-   Assigned product and operation
-   Current shift
-   Station status

The system must record assignment history. If a worker changes stations
or a station changes workers, events and production records must remain
linked to the correct worker, station, and time period.

------------------------------------------------------------------------

## 6. Worker Activity Monitoring

### 6.1 Working-Time Measurement

The system should estimate how much of a scheduled shift is spent in
defined states.

Suggested activity states:

-   **Productive / sewing activity:** Worker is performing the assigned
    sewing operation.
-   **Machine running:** Machine activity is detected; this does not
    automatically prove that acceptable production is being completed.
-   **Idle:** No expected work activity is detected for a configured
    period.
-   **Break:** A scheduled or authorized break is in progress.
-   **Phone use:** A defined phone-use event is detected during a period
    when work is scheduled.
-   **Other / uncertain:** The system cannot confidently classify the
    activity.
-   **Machine downtime:** Machine is stopped because of a machine or
    operational issue.
-   **Material / setup delay:** Work is paused for material, setup, or
    other recorded reasons.

The system should not classify every pause as worker idleness. Sewing
work may naturally include fabric handling, thread adjustment, garment
repositioning, quality checks, and other legitimate non-sewing tasks.

### 6.2 Time Calculation

Let:

-   `Shift Duration` = configured shift end minus shift start.
-   `Scheduled Break Duration` = total authorized breaks.
-   `Scheduled Work Duration` = shift duration minus scheduled breaks.
-   `Productive Time` = time classified as productive work.
-   `Idle Time` = time classified as idle after applying configured
    rules.
-   `Phone-Use Time` = time classified as phone use during scheduled
    work.
-   `Machine Downtime` = time machine is unavailable or stopped for a
    recorded reason.
-   `Uncertain Time` = time that cannot be confidently classified.

Basic calculation:

``` text
Scheduled Work Duration = Shift Duration - Scheduled Break Duration

Accounted Time =
    Productive Time
  + Idle Time
  + Phone-Use Time
  + Machine Downtime
  + Other Recorded Time
  + Uncertain Time
```

The categories and overlap rules must be defined so the same minute is
not counted twice.

A possible productivity-time ratio is:

``` text
Productive Time Ratio =
    Productive Time / Scheduled Work Duration * 100
```

This ratio should be reported with data coverage and uncertainty. It
should not be used as the only worker-performance measure.

### 6.3 Phone-Use Detection

Computer vision may detect a phone-like object and a worker interaction
pattern. However, a camera cannot always determine with certainty
whether a worker is using a phone, and a phone may be hidden, outside
the camera view, or confused with another object.

Recommended approach:

-   Detect a phone-like object in the relevant station area.
-   Estimate whether the worker is interacting with it.
-   Apply a minimum event duration and confidence threshold.
-   Store event start/end time and confidence.
-   Allow supervisor review or correction.
-   Avoid recording personal screen content or audio.

The system should report a probable phone-use event, not claim certainty
when evidence is ambiguous.

### 6.4 Idle-Time Detection

Idle detection should combine multiple signals:

-   Worker posture and activity from camera analysis.
-   Sewing-machine running / stopped signal.
-   Production event timestamps.
-   Configured operation workflow.
-   Known breaks, setup periods, and downtime records.

An idle event should only be generated after a configurable duration
threshold. Legitimate pauses should have reason codes or supervisor
correction options.

------------------------------------------------------------------------

## 7. Production Output Measurement

The platform should calculate how many products or operation units a
worker completes during a shift.

### 7.1 Counting methods

Possible methods include:

1.  **Computer vision:** Detect a completed item or a defined production
    handoff at a camera-visible point.
2.  **Machine or production sensors:** Detect operation cycles or
    machine events where the machine supports reliable signals.
3.  **Production-system integration:** Import confirmed production
    counts from an existing factory system.
4.  **Operator / supervisor confirmation:** Provide a manual correction
    or confirmation workflow.

The preferred approach depends on the product, sewing operation, camera
position, and factory workflow.

### 7.2 Important distinction

A machine cycle, a stitch, a completed sewing operation, and a finished
garment are not the same unit.

The factory must define the counting unit for each operation. For
example, one station may sew a sleeve seam while another attaches a
collar. Their raw counts should not be directly compared as if each unit
required equal effort.

### 7.3 Suggested production metrics

-   Total detected units
-   Confirmed accepted units
-   Rejected / rework units
-   Units per productive hour
-   Units per scheduled work hour
-   Target achievement percentage
-   Production trend by hour, shift, day, and week

Example formulas:

``` text
Units per Productive Hour =
    Confirmed Accepted Units / Productive Hours

Target Achievement =
    Confirmed Accepted Units / Assigned Target * 100

First-Pass Acceptance Rate =
    Accepted Units Without Rework / Total Inspected Units * 100
```

Use the actual factory-approved production definition and inspection
result.

------------------------------------------------------------------------

## 8. Sewing Quality Monitoring

### 8.1 Skipped-Stitch Detection

A skipped stitch occurs when the expected stitch is not properly formed
even though the sewing process continues. The project discussion
describes this as a situation where the machine runs but sewing is not
properly completed.

This is a key quality-monitoring requirement.

**Can a camera detect it?** Potentially, yes, if the camera can see the
seam clearly and the fabric is presented in a suitable inspection
position. However, detecting a missing stitch in a moving fabric stream
can be difficult because:

-   Stitches may be very small.
-   Fabric moves quickly.
-   The needle and presser foot may hide the seam.
-   Fabric patterns, folds, lighting, and thread color can affect
    visibility.
-   The system may need close-up images after the seam is sewn.

### 8.2 Recommended detection approach

A practical design may combine:

-   A close-up camera positioned to inspect the sewn seam.
-   Controlled lighting and a stable inspection field.
-   Computer-vision analysis of stitch continuity and spacing.
-   A post-sewing inspection point where the seam is visible.
-   Optional machine signals to identify when sewing is occurring.

The model should return a result such as:

-   No visible defect detected
-   Possible skipped stitch
-   Other visible seam defect
-   Image not suitable for inspection
-   Needs human inspection

A human quality inspector should validate uncertain or high-impact cases
during the pilot.

### 8.3 Other quality observations

The initial project may also record seam puckering or other visible
defects if the camera angle and image quality support them. Each defect
type should have its own definition, training data, confidence
threshold, and validation process.

------------------------------------------------------------------------

## 9. Needle-Break Detection and Analysis

### 9.1 The challenge

Needles are small and move very rapidly. The project discussion
estimates approximately 20--70 movements or bounces per second. A normal
CCTV camera may not capture a needle break reliably because of:

-   Very small needle size
-   High movement speed
-   Motion blur
-   Occlusion by fabric, presser foot, and machine parts
-   Camera frame-rate and resolution limitations
-   Different machine designs and needle positions

Therefore, ordinary wide-angle CCTV should not be treated as a
dependable standalone needle-break detector.

### 9.2 Recommended technical options

The final sensor choice must be validated on the actual sewing machines.

  -----------------------------------------------------------------------
  Method                  Possible role           Limitations
  ----------------------- ----------------------- -----------------------
  Machine event / alarm   Read a break or stop    Depends on machine
  signal                  event if the machine    model and available
                          exposes one             interface

  Optical sensor          Detect a change in a    Requires suitable
                          needle-related or       mounting and
                          machine-related         calibration
                          position / signal       

  Vibration / acoustic    Detect an abnormal      Noise and machine
  sensor                  event or machine        variation may cause
                          signature               false positives

  Thread-tension /        Detect thread-related   Thread break is not the
  thread-break sensor     abnormality             same as needle break

  High-speed close-up     Capture needle movement Higher cost, careful
  camera                  for specialized         lighting and
                          analysis                installation required

  Operator / supervisor   Confirm and classify an Manual and not fully
  confirmation            event                   automatic
  -----------------------------------------------------------------------

**Recommended initial direction:** Investigate machine-provided
needle-break or machine-stop signals first. If unavailable, prototype an
appropriate optical or other sensor with machine technicians. Use camera
footage as supporting evidence rather than assuming it can directly
observe every break.

### 9.3 Event workflow

``` text
Needle-related abnormal event
          |
          v
Machine signal / sensor event
          |
          v
Create a timestamped event
          |
          v
Link to station, worker, machine, and needle batch
          |
          v
Supervisor confirmation / event classification
          |
          v
Update needle-break analytics
```

The system should distinguish:

-   Confirmed needle break
-   Suspected needle break
-   Thread break
-   Machine stop / jam
-   Other machine fault
-   Unknown event

This distinction is essential because these events have different
causes.

------------------------------------------------------------------------

## 10. Needle Supplier and Batch Quality Analytics

A major project requirement is to determine whether repeated needle
breaks may be associated with a supplier or a specific needle batch,
rather than automatically blaming a worker.

### 10.1 Traceability data

For each needle batch, record:

-   Supplier / manufacturer
-   Needle brand and model
-   Needle type and size
-   Batch / lot number
-   Purchase or receiving date
-   Quantity received
-   Quantity issued to production
-   Station and machine where used
-   Worker assignment during use
-   Installation / replacement date
-   Confirmed break count
-   Other failure or inspection notes

### 10.2 Example scenario

Suppose a factory receives 20 needles from one supplier batch, and 10
are confirmed broken during use.

``` text
Received from Supplier A, Batch B-104: 20 needles
Confirmed broken: 10 needles
Observed break proportion: 10 / 20 = 50%
```

This is a signal that the batch should be investigated. It does not by
itself prove that the supplier is responsible. The factory should
compare usage conditions, machine compatibility, operation type,
installation, and exposure time.

### 10.3 Distinguishing batch issues from station / worker issues

The system should compare patterns:

  -----------------------------------------------------------------------
  Pattern                             Possible explanation to investigate
  ----------------------------------- -----------------------------------
  Multiple workers and machines show  Possible batch or needle-model
  elevated breaks for one batch       issue

  One station has repeated breaks     Possible machine alignment,
  across different batches and        maintenance, or station issue
  workers                             

  One worker has repeated breaks      Possible handling, technique, or
  across different machines and       training issue
  batches                             

  Breaks occur across many stations   Possible operation or
  using the same operation/material   material-related issue

  One machine shows repeated breaks   Possible machine condition or setup
  regardless of worker or batch       issue
  -----------------------------------------------------------------------

These are investigation clues, not automatic conclusions.

### 10.4 Fair comparison

A simple break percentage can be misleading if batches have different
usage volumes.

Where possible, calculate:

``` text
Needle Break Rate =
    Confirmed Needle Breaks / Needles Issued * 100
```

Also track exposure, such as operating hours, production units, or
machine cycles:

``` text
Breaks per 1,000 Operating Hours =
    Confirmed Needle Breaks / Operating Hours * 1000
```

Use a consistent denominator and compare like with like. Do not compare
a new batch with very little usage against an older batch without
considering exposure.

### 10.5 Investigation and action

When a batch or station exceeds a configurable threshold:

1.  Create an alert for the quality / maintenance team.
2.  Review the affected batch, stations, machines, and operations.
3.  Confirm the event classifications.
4.  Inspect the needle and machine condition.
5.  Record the investigation outcome.
6.  Decide whether to quarantine a batch, service a machine, revise
    setup, or provide worker coaching.
7.  Track whether the issue improves after the action.

------------------------------------------------------------------------

## 11. Worker Performance Analytics and Ranking

### 11.1 Ranking principle

Workers may be ranked using production and quality data. However,
ranking only by the number of products produced can be unfair when
workers perform different operations, work with different materials, or
face different machine conditions.

The system should compare workers performing comparable work, or
normalize performance against operation-specific standards.

### 11.2 Suggested metrics

-   Confirmed accepted production
-   Production per productive hour
-   Target achievement
-   Quality acceptance rate
-   Rework / defect rate
-   Productive-time ratio
-   Recorded machine downtime
-   Operation difficulty / standard time
-   Data coverage and confidence

Phone-use or idle events should be treated as operational indicators
that require context and review, not as the sole basis for a ranking.

### 11.3 Example scoring framework

An illustrative configurable score could be:

``` text
Worker Performance Score =
    (Normalized Production Score * Production Weight)
  + (Quality Score * Quality Weight)
  + (Productive-Time Score * Time Weight)
```

The weights must be configured and approved by the factory. They should
total 100%.

Example only:

  Metric                      Example weight
  ------------------------- ----------------
  Normalized production                  50%
  Quality / acceptance                   35%
  Productive-time measure                15%
  **Total**                         **100%**

These are example values, not a final policy. The admin should be able
to change weights, eligibility rules, and reporting periods.

### 11.4 Ranking safeguards

-   Compare workers with similar operations and product difficulty.
-   Exclude or separately account for authorized breaks.
-   Account for machine downtime and material shortages.
-   Use confirmed production and quality records where possible.
-   Require a minimum data-coverage threshold.
-   Show the reason behind a score.
-   Allow authorized review and correction.
-   Avoid ranking workers on incomplete or unreliable data.

### 11.5 Bonus eligibility

The system may generate a bonus-eligibility list based on
administrator-defined rules.

Possible criteria:

-   Minimum production target achievement
-   Minimum quality acceptance rate
-   Minimum data coverage
-   Required working-period completion
-   No unresolved critical data issue

The system should provide a recommendation and supporting metrics. Final
bonus approval should remain with authorized management under the
factory's policy.

------------------------------------------------------------------------

## 12. Training and Coaching Recommendations

The system should identify workers who may benefit from training, not
automatically label them as unqualified.

Potential indicators:

-   Repeated quality defects
-   Low normalized production against comparable operations
-   Repeated needle-break events associated with a worker after other
    causes are investigated
-   Difficulty maintaining the required operation quality
-   Repeated need for rework
-   Supervisor observations

### 12.1 Decision workflow

``` text
Performance / quality indicator detected
                |
                v
Check data quality and confidence
                |
                v
Check machine, material, operation, and batch factors
                |
                v
Supervisor reviews the evidence
                |
         +------+------+
         |             |
         v             v
   External issue   Worker skill gap
         |             |
         v             v
 Machine / batch    Coaching or training
 investigation      recommendation
         |             |
         +------+------+
                |
                v
       Follow-up evaluation
```

### 12.2 Training record

A training record may contain:

-   Worker ID
-   Recommended skill / operation
-   Reason for recommendation
-   Supporting quality or production indicators
-   Supervisor decision
-   Training date
-   Trainer / responsible person
-   Follow-up evaluation
-   Result after training

A worker should not be sent to training solely because of needle breaks
until batch, machine, material, and operation factors have been
considered.

------------------------------------------------------------------------

## 13. Dynamic Admin Configuration

A central requirement is that each factory may have different
working-hour limits and production policies. The system must not
hard-code one factory's rules.

### 13.1 Configurable policy categories

  Category           Example settings
  ------------------ ----------------------------------------------
  Shift              Start time, end time, duration, night shift
  Break              Lunch duration, short breaks, break windows
  Work limits        Daily / weekly limits, overtime policy
  Station            Number of lines, stations, machines
  Worker             Assignment, role, skill, operation
  Production         Target by operation, product, shift
  Quality            Defect types, thresholds, inspection rules
  Needle             Supplier, model, batch, alert thresholds
  Ranking            Metrics, weights, eligibility, review period
  Training           Thresholds, approval flow, follow-up period
  Alerts             Severity, recipients, notification channels
  Camera / sensors   Device mapping, zones, calibration
  Data policy        Retention period, access, audit rules

### 13.2 Admin capabilities

-   Create, edit, activate, or deactivate policies.
-   Configure multiple shifts and break schedules.
-   Configure different rules for different factories, lines, and
    operations.
-   Change ranking weights and thresholds.
-   Manage worker and machine assignments.
-   Register needle suppliers and batches.
-   Map cameras and sensors to stations.
-   Review and correct detected events.
-   Export reports.
-   View configuration history and audit logs.

Changes to policies should be versioned. Historical records should
retain the policy version that applied when the event occurred.

------------------------------------------------------------------------

## 14. Proposed System Architecture

The following is a logical architecture. The exact hardware, model,
framework, and deployment choices should be finalized after a
factory-site survey and pilot.

``` mermaid
flowchart TB
    subgraph FLOOR["Sewing Floor"]
        CAM["Station Cameras"]
        MACH["Sewing Machines"]
        SENS["Machine / Optical / Other Sensors"]
        WORK["Workers and Production Operations"]
    end

    subgraph EDGE["Edge / Station Processing"]
        VIDEO["Video Stream Processing"]
        CV["Computer Vision Models"]
        SENSOR["Sensor and Machine Event Collector"]
        EVENT["Timestamped Station Events"]
    end

    subgraph PLATFORM["Central Platform"]
        API["Backend API"]
        RULES["Configurable Rules Engine"]
        DB[("Operational Database")]
        FILES[("Video Evidence / Image Storage")]
        ANALYTICS["Analytics and Scoring Engine"]
        ALERTS["Alert and Notification Service"]
    end

    subgraph USERS["Application"]
        ADMIN["Admin Dashboard"]
        SUP["Supervisor Dashboard"]
        QUALITY["Quality / Maintenance Dashboard"]
        REPORT["Reports and Worker Views"]
    end

    CAM --> VIDEO
    VIDEO --> CV
    MACH --> SENSOR
    SENS --> SENSOR
    WORK --> CV
    CV --> EVENT
    SENSOR --> EVENT
    EVENT --> API
    API --> RULES
    API --> DB
    API --> FILES
    RULES --> ANALYTICS
    DB --> ANALYTICS
    ANALYTICS --> ALERTS
    API --> ADMIN
    API --> SUP
    API --> QUALITY
    ANALYTICS --> REPORT
```

### 14.1 Architecture responsibilities

-   **Station cameras:** Capture the relevant work area and, where
    appropriate, close-up quality inspection views.
-   **Machine / other sensors:** Provide machine state or needle-related
    events where technically available.
-   **Edge processing:** Process video close to the station where
    practical, reduce unnecessary video transfer, and create timestamped
    events.
-   **Computer vision:** Classify defined activities and inspect visible
    production / seam features.
-   **Backend API:** Manage users, stations, assignments, events,
    policies, and reports.
-   **Rules engine:** Apply factory-specific schedules, thresholds, and
    eligibility policies.
-   **Database:** Store structured operational records and traceability.
-   **Analytics engine:** Calculate time, output, quality, ranking, and
    batch-level indicators.
-   **Dashboards:** Present the information to authorized users.

------------------------------------------------------------------------

## 15. Computer Vision and Sensor Modules

Each model or detector should have a narrowly defined task and a
measurable validation target.

  -----------------------------------------------------------------------
  Module            Input             Expected output   Important
                                                        limitation
  ----------------- ----------------- ----------------- -----------------
  Worker presence / Station video     Activity state    Camera view and
  activity                            and confidence    occlusion affect
                                                        results

  Phone-use event   Station video     Probable phone    Cannot always
                                      interaction event establish intent

  Idle-state        Video + machine   Possible idle     Must exclude
  estimation        state             interval          legitimate pauses

  Production        Video / machine / Counted operation Unit definition
  counting          production events units             and validation
                                                        required

  Seam inspection   Close-up seam     Possible skipped  Requires visible,
                    image             stitch / defect   suitable images

  Needle-break      Machine signal /  Confirmed or      CCTV alone may be
  event             sensor            suspected event   insufficient

  Machine state     Machine interface Running, stopped, Depends on
                    / sensor          fault where       machine
                                      available         compatibility
  -----------------------------------------------------------------------

### 15.1 Model output format

A common event structure should include:

-   `event_id`
-   `factory_id`
-   `station_id`
-   `machine_id`
-   `worker_id` where assignment is known
-   `event_type`
-   `start_time`
-   `end_time`
-   `confidence`
-   `source_device_id`
-   `model_version` or `sensor_version`
-   `review_status`
-   `reviewed_by`
-   `reviewed_at`
-   `metadata`

Do not store a model prediction as a confirmed fact without the required
validation workflow.

------------------------------------------------------------------------

## 16. Suggested Database Structure

The following is a conceptual entity list, not a final database
migration.

``` mermaid
erDiagram
    FACTORY ||--o{ FLOOR : contains
    FLOOR ||--o{ PRODUCTION_LINE : contains
    PRODUCTION_LINE ||--o{ STATION : contains
    STATION ||--|| MACHINE : has
    STATION ||--o{ DEVICE : uses
    WORKER ||--o{ WORKER_ASSIGNMENT : assigned
    STATION ||--o{ WORKER_ASSIGNMENT : receives
    SHIFT_POLICY ||--o{ SHIFT_RECORD : defines
    WORKER ||--o{ SHIFT_RECORD : works
    STATION ||--o{ PRODUCTION_EVENT : records
    WORKER ||--o{ PRODUCTION_EVENT : produces
    MACHINE ||--o{ MACHINE_EVENT : generates
    WORKER ||--o{ ACTIVITY_EVENT : has
    STATION ||--o{ QUALITY_EVENT : records
    NEEDLE_SUPPLIER ||--o{ NEEDLE_BATCH : supplies
    NEEDLE_BATCH ||--o{ NEEDLE_ISSUE : issued
    STATION ||--o{ NEEDLE_ISSUE : uses
    NEEDLE_BATCH ||--o{ NEEDLE_EVENT : associated
    WORKER ||--o{ TRAINING_RECORD : receives
    WORKER ||--o{ PERFORMANCE_SNAPSHOT : evaluated
    ADMIN_USER ||--o{ AUDIT_LOG : creates
```

### 16.1 Suggested core tables

  -----------------------------------------------------------------------
  Table                               Purpose
  ----------------------------------- -----------------------------------
  `factories`                         Factory information

  `floors`                            Factory floors

  `production_lines`                  Production lines

  `stations`                          Sewing stations

  `machines`                          Sewing machine details

  `devices`                           Cameras and sensors

  `workers`                           Worker profiles

  `worker_assignments`                Time-bound worker-to-station
                                      assignments

  `shift_policies`                    Configurable shift and break
                                      policies

  `shift_records`                     Actual worker shift records

  `activity_events`                   Productive, idle, phone-use, break,
                                      and uncertain events

  `machine_events`                    Running, stopped, and machine fault
                                      events

  `production_events`                 Detected or confirmed production
                                      units

  `quality_events`                    Skipped-stitch and other defect
                                      records

  `needle_suppliers`                  Supplier information

  `needle_models`                     Needle type, model, and size

  `needle_batches`                    Batch / lot traceability

  `needle_issues`                     Needle issue and station usage
                                      records

  `needle_events`                     Break and other needle-related
                                      events

  `performance_snapshots`             Periodic worker performance
                                      calculations

  `ranking_policies`                  Configurable ranking weights and
                                      rules

  `training_records`                  Coaching and training
                                      recommendations / outcomes

  `bonus_records`                     Bonus recommendations and approvals

  `admin_users`                       Authorized application users

  `audit_logs`                        Configuration and decision history
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Dashboard Requirements

### 17.1 Admin Dashboard

-   Factory-wide overview
-   Active / inactive stations
-   Worker and machine management
-   Shift and break configuration
-   Production targets
-   Ranking policy settings
-   Needle supplier and batch management
-   Camera / sensor health
-   Alerts and audit history

### 17.2 Supervisor Dashboard

-   Live station status
-   Worker activity timeline
-   Production count and target progress
-   Idle and downtime events
-   Possible phone-use events for review
-   Worker assignment changes
-   Supervisor event confirmation

### 17.3 Quality Dashboard

-   Skipped-stitch and defect trends
-   Defect rates by operation / station / machine
-   Rework and acceptance rates
-   Inspection images or evidence where authorized
-   Quality-event review and disposition

### 17.4 Needle and Maintenance Dashboard

-   Needle breaks by supplier and batch
-   Breaks by machine, station, worker, and operation
-   Needle usage and replacement history
-   Machine fault and downtime trends
-   Batch / station investigation alerts
-   Investigation outcomes

### 17.5 Performance Dashboard

-   Worker performance by comparable operation
-   Production per productive hour
-   Quality and acceptance metrics
-   Target achievement
-   Ranking and score explanation
-   Bonus eligibility recommendations
-   Training recommendations and follow-up results

------------------------------------------------------------------------

## 18. Example End-to-End Workflows

### 18.1 Daily worker monitoring

``` mermaid
flowchart TD
    A["Worker starts assigned shift"] --> B["Load active shift and break policy"]
    B --> C["Monitor camera and machine / sensor events"]
    C --> D["Classify activity and record production events"]
    D --> E["Identify possible idle, phone-use, and downtime events"]
    E --> F["Supervisor reviews uncertain events"]
    F --> G["Calculate shift time and confirmed production"]
    G --> H["Generate shift report"]
```

### 18.2 Needle-break investigation

``` mermaid
flowchart TD
    A["Needle-related event detected"] --> B["Record timestamp and source"]
    B --> C["Link station, machine, worker, and needle batch"]
    C --> D["Confirm event type"]
    D --> E["Aggregate by batch, machine, operation, and worker"]
    E --> F{"Repeated pattern above configured threshold?"}
    F -->|Batch pattern| G["Investigate supplier / batch"]
    F -->|Machine pattern| H["Inspect machine and setup"]
    F -->|Worker pattern| I["Review technique and training needs"]
    F -->|No clear pattern| J["Continue monitoring"]
    G --> K["Record investigation and corrective action"]
    H --> K
    I --> K
    J --> L["Reassess with more data"]
```

### 18.3 Performance and training review

``` mermaid
flowchart TD
    A["End of reporting period"] --> B["Validate data coverage"]
    B --> C["Normalize by operation and working conditions"]
    C --> D["Calculate production and quality metrics"]
    D --> E["Apply active ranking policy"]
    E --> F["Generate ranking and bonus recommendations"]
    D --> G["Identify possible coaching needs"]
    G --> H["Supervisor reviews evidence and external causes"]
    H --> I["Approve coaching / training or close recommendation"]
    I --> J["Evaluate results after training"]
```

------------------------------------------------------------------------

## 19. Alerts and Notifications

Suggested alert types:

  -----------------------------------------------------------------------
  Alert                   Trigger example         Recipient
  ----------------------- ----------------------- -----------------------
  Possible prolonged idle Idle state exceeds      Supervisor
                          configured duration     

  Possible phone use      Probable event exceeds  Supervisor
                          configured duration     

  Machine stopped         Machine stop exceeds    Maintenance /
                          configured duration     supervisor

  Possible skipped stitch Quality model detects a Quality team
                          possible defect         

  Needle-break event      Sensor or machine event Supervisor /
                          indicates a possible    maintenance
                          break                   

  Batch break-rate        Batch metric exceeds    Quality / procurement
  warning                 configured threshold    

  Station abnormality     Repeated machine or     Maintenance
                          quality events          

  Device offline          Camera or sensor stops  Technical administrator
                          reporting               

  Training recommendation Reviewed metrics meet   Supervisor / training
                          configured criteria     team
  -----------------------------------------------------------------------

Alerts should include severity, timestamp, station, event type,
confidence, and review status.

------------------------------------------------------------------------

## 20. Security, Privacy, and Responsible Use

Because the platform monitors workers, privacy and responsible use must
be part of the design.

-   Inform workers about monitoring purposes, monitored areas, and
    applicable policies.
-   Obtain required organizational approvals and comply with applicable
    laws.
-   Use role-based access control.
-   Limit camera views to necessary work areas.
-   Avoid audio recording unless separately justified, approved, and
    legally permitted.
-   Do not use facial recognition unless there is a separately approved
    and necessary use case.
-   Prefer event metadata over continuous video retention.
-   Define retention periods and secure deletion rules.
-   Encrypt data in transit and at rest.
-   Maintain audit logs for access, policy changes, and manual
    corrections.
-   Provide a way to challenge or correct inaccurate events.
-   Keep human review for consequential bonus, training, and employment
    decisions.
-   Show confidence and data coverage; do not present uncertain AI
    outputs as confirmed facts.

The system should measure work processes and production conditions
fairly, not infer a worker's intentions or character from video.

------------------------------------------------------------------------

## 21. Non-Functional Requirements

  -----------------------------------------------------------------------
  Area                                Requirement
  ----------------------------------- -----------------------------------
  Reliability                         Handle temporary camera, network,
                                      and sensor interruptions

  Scalability                         Support multiple lines, floors, and
                                      factories

  Performance                         Process events with a latency
                                      suitable for the selected use case

  Availability                        Provide clear device and service
                                      health status

  Security                            Authentication, authorization,
                                      encryption, and audit logs

  Maintainability                     Modular services and versioned
                                      models / policies

  Explainability                      Show why an event or score was
                                      generated

  Data quality                        Track missing, duplicate, and
                                      uncertain events

  Configurability                     Avoid hard-coded factory schedules
                                      and thresholds

  Interoperability                    Support machine interfaces and
                                      existing factory systems where
                                      available
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 22. Pilot Plan and Validation

A pilot should be completed before factory-wide deployment.

### Phase 1 --- Site survey

-   Identify sewing-machine models and available machine signals.
-   Map stations, worker assignments, lighting, camera angles, and
    network conditions.
-   Observe the real production workflow.
-   Define the production counting unit for each operation.
-   Document needle types, suppliers, and batch practices.
-   Confirm shift, break, and overtime policies.

### Phase 2 --- Data collection

-   Collect representative camera samples with appropriate notice and
    approvals.
-   Collect machine running / stop signals where available.
-   Record confirmed production counts.
-   Record verified needle-break events and their causes.
-   Collect examples of skipped stitches and acceptable seams.
-   Label data with supervisor / quality-team input.

### Phase 3 --- Prototype

-   Build station and worker configuration.
-   Implement activity-state estimation.
-   Prototype production counting.
-   Test seam inspection on close-up images.
-   Prototype needle-break sensing with machine technicians.
-   Build event storage and review dashboards.

### Phase 4 --- Validation

Measure each component separately:

-   Activity classification precision and recall
-   Phone-use event precision and recall
-   Idle detection accuracy against reviewed samples
-   Production-count error against manual counts
-   Skipped-stitch detection precision and recall
-   Needle-break detection precision and recall
-   Event timestamp accuracy
-   Camera / sensor uptime
-   Worker assignment and traceability accuracy

Do not launch bonus or training automation until the data and scoring
methods have been validated and reviewed.

### Phase 5 --- Controlled deployment

-   Start with a small number of stations.
-   Run the system in observation mode.
-   Compare results with manual records.
-   Fix false positives and missed events.
-   Train supervisors and administrators.
-   Expand gradually after acceptance criteria are met.

------------------------------------------------------------------------

## 23. Key Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                    Impact                  Mitigation
  ----------------------- ----------------------- -----------------------
  Needle is too small /   Missed or false         Use machine signals or
  fast for CCTV           needle-break events     validated sensors

  Camera cannot see the   Skipped stitches are    Add close-up inspection
  seam clearly            missed                  position and controlled
                                                  lighting

  Different operations    Unfair worker ranking   Normalize by operation
  have different                                  and standard time
  difficulty                                      

  Worker changes station  Incorrect worker        Use time-bound
                          attribution             assignment history

  Machine runs without    Inflated production     Separate machine state
  acceptable sewing       estimate                from confirmed
                                                  production and quality

  Fabric / lighting       Computer-vision errors  Collect diverse
  variation                                       training data and
                                                  monitor model
                                                  performance

  Legitimate pauses look  Unfair activity reports Combine machine
  like idleness                                   context, workflow
                                                  states, and human
                                                  review

  Bad needle batch blamed Incorrect training      Track supplier, batch,
  on worker               decision                machine, operation, and
                                                  exposure

  Missing or unreliable   Incorrect analytics     Show data coverage and
  sensor data                                     mark incomplete periods

  Policy changes alter    Inconsistent historical Version policies and
  score meaning           reports                 preserve historical
                                                  versions
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 24. Suggested Development Roadmap

  -----------------------------------------------------------------------
  Stage                               Deliverables
  ----------------------------------- -----------------------------------
  1\. Requirements and site survey    Confirm machine types, workflow,
                                      policies, and station layout

  2\. Platform foundation             Authentication, roles, factory,
                                      line, station, worker, and machine
                                      management

  3\. Dynamic configuration           Shift, break, work-limit,
                                      production, ranking, and alert
                                      settings

  4\. Event ingestion                 Camera / sensor integration and
                                      timestamped event pipeline

  5\. Worker activity module          Activity, idle, phone-use, and
                                      working-time estimates

  6\. Production module               Operation-specific production
                                      counting and confirmation

  7\. Quality module                  Skipped-stitch / seam inspection
                                      prototype

  8\. Needle module                   Needle-break sensing and batch
                                      traceability

  9\. Analytics module                Performance, ranking, supplier, and
                                      training insights

  10\. Dashboards and reports         Admin, supervisor, quality,
                                      maintenance, and performance
                                      dashboards

  11\. Pilot and validation           Ground-truth comparison, error
                                      analysis, and policy review

  12\. Deployment                     Controlled rollout, monitoring,
                                      maintenance, and improvement
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 25. Open Questions Before Final Technical Design

The following points require factory input. They are intentionally left
open rather than assumed.

1.  Which sewing-machine brands and models are installed?
2.  Do the machines expose needle-break, thread-break, motor-running, or
    machine-stop signals?
3.  How many stations, machines, workers, floors, and production lines
    are in the first deployment?
4.  Can workers move between stations during a shift?
5.  What exactly counts as one production unit for each sewing
    operation?
6.  Is production counted per completed seam, operation piece, garment
    part, or finished product?
7.  Where can a close-up camera inspect the seam after sewing?
8.  What needle suppliers, models, and batch identifiers are currently
    recorded?
9.  How are needle issues and replacements recorded today?
10. What are the factory's shift, break, overtime, and weekly work-limit
    policies?
11. What production and quality rules are currently used for bonuses and
    training?
12. What privacy, worker-notice, and video-retention policies apply?

------------------------------------------------------------------------

## 26. Initial Recommended Technical Direction

Based on the project requirements, a hybrid approach is more practical
than trying to solve every problem with CCTV alone.

  -----------------------------------------------------------------------
  Requirement                         Initial recommended direction
  ----------------------------------- -----------------------------------
  Worker activity                     Camera-based computer vision

  Phone-use event                     Camera-based object / interaction
                                      detection with review

  Idle-time estimation                Camera + machine state + schedule

  Product counting                    Operation-specific vision and/or
                                      machine / production signals

  Skipped-stitch detection            Close-up seam inspection with
                                      computer vision

  Needle-break detection              Machine event or validated sensor;
                                      camera as supporting evidence

  Needle batch analysis               Structured supplier, batch, issue,
                                      and event records

  Worker ranking                      Configurable, operation-normalized
                                      analytics

  Training recommendation             Evidence-based rules with
                                      supervisor review

  Factory-specific working limits     Dynamic admin policy configuration
  -----------------------------------------------------------------------

### Design principle

**Use the right evidence source for each problem.** Cameras are useful
for visible worker activity and seam inspection. Machine signals and
sensors are better candidates for fast, hidden mechanical events.
Production records establish confirmed output. Combining these sources
gives a more reliable view of the sewing floor.

------------------------------------------------------------------------

## 27. Glossary

  -----------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- -----------------------------------
  Sewing station                      A sewing machine work area, usually
                                      assigned to a worker

  Productive time                     Time classified as active work
                                      under the configured operation

  Idle time                           A period with no expected work
                                      activity after configured rules

  Machine downtime                    A period when the machine is
                                      unavailable or stopped

  Production unit                     The factory-defined unit counted
                                      for a particular operation

  Skipped stitch                      A missing or improperly formed
                                      stitch in a seam

  Needle break                        Physical breakage of the sewing
                                      needle

  Thread break                        Breakage of sewing thread; not the
                                      same as needle break

  Needle batch / lot                  A traceable group of needles from a
                                      supplier or production lot

  First-pass acceptance               Output accepted without rework

  Performance normalization           Adjusting comparisons for operation
                                      difficulty and working conditions

  Edge processing                     Processing data near the camera or
                                      machine rather than sending all raw
                                      data to a central server
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 28. Conclusion

The proposed platform is a configurable textile sewing-floor
intelligence system. It connects worker activity monitoring,
machine-state information, production counting, seam-quality inspection,
needle-break tracking, supplier-batch analysis, and performance
analytics.

Its most important design requirement is to avoid drawing conclusions
from a single signal. A machine running does not prove that a product
has been completed. A needle break does not automatically prove worker
error. Low output does not automatically mean poor performance. The
system should combine evidence, account for working conditions, expose
uncertainty, and support human review.

The first implementation should focus on reliable station configuration,
shift tracking, machine-state collection, production confirmation, and
event review. Computer-vision and sensor models should then be
introduced and validated one use case at a time.

**Final product vision:** A smart, data-driven sewing-floor management
platform that helps factories improve productivity, quality, equipment
reliability, supplier accountability, and worker development through
transparent and configurable analytics.
