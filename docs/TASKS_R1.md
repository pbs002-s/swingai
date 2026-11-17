# R1 Task List — Platform MVP

**Audience:** development team
**Status:** Draft v1 — 2026-11-17
**Related:** [PRD](PRD.md) §4 · [TRD](TRD.md) · [Backend Design](BACKEND_DESIGN.md) · [API](API.md)

R1 delivers the full platform working on **manual entry + simulated events**: no cameras or sensors yet. Alerts are included in R1 because the admin dashboard must show them.

Tasks are in build order. `Needs` lists the tasks that must be finished first. Each task is done when its "Done when" is true **and** its tests pass in CI.

The frontend can start with default shadcn/ui styling and is restyled when the UI design arrives (task W-12).

---

## Phase 0 — Project setup

| ID | Task | Needs | Done when |
|---|---|---|---|
| S-1 | Monorepo layout (`apps/web`, `apps/api`, `apps/worker`, `tools/simulator`, `deploy`, `docs`) | — | Folders + root README stub exist |
| S-2 | `deploy/docker-compose.yml`: postgres 16, redis 7, minio, caddy, api, worker, web | S-1 | `docker compose up` starts all services; `/api/v1/healthz` returns 200 |
| S-3 | `.env.example` + startup validation of required settings | S-2 | API refuses to start with a clear message if a required setting is missing |
| S-4 | Backend tooling: ruff, mypy, pytest, testcontainers Postgres | S-1 | `make test-api` runs green on an empty test |
| S-5 | Frontend tooling: Next.js 15, TypeScript strict, ESLint, Vitest, Playwright | S-1 | `npm test` and `npm run build` pass |
| S-6 | GitHub Actions CI: lint, type-check, test, build images, pip-audit, npm audit | S-4, S-5 | CI runs on every push |

## Phase 1 — Backend core

| ID | Task | Needs | Done when |
|---|---|---|---|
| C-1 | `core/`: settings, async DB session, Alembic, response envelope, error codes, pagination/sort/filter helpers | S-4 | Unit tests for envelope and pagination |
| C-2 | Request ID + structured JSON logging + `/readyz` (DB, Redis, MinIO checks) | C-1 | Logs carry request ID; readyz fails when DB is down |
| C-3 | Translatable error messages (`en`, `bn`) driven by `Accept-Language` | C-1 | Same error code returns both languages |
| C-4 | Optimistic locking helper (`version` + `If-Match`) | C-1 | Stale update returns 409 `VERSION_CONFLICT` |

## Phase 2 — Auth, users, audit

| ID | Task | Needs | Done when |
|---|---|---|---|
| A-1 | `users`, `roles`, `user_roles` tables + seed roles + first system admin from env | C-1 | Migration runs; admin can log in |
| A-2 | Login / logout / me; Argon2id; session cookie; CSRF; lockout after 10 failures; login rate limit | A-1 | Integration tests for each case |
| A-3 | RBAC dependency + factory/line scope filter, applied to every router | A-2 | Test matrix: each role × sample endpoints gives the expected 200 / 403 / 404 |
| A-4 | User management endpoints (create, edit, deactivate, reset password, set roles) | A-3 | API.md §3 covered |
| A-5 | `audit_logs` + automatic before/after capture on every mutating service call | A-1 | Editing any record writes an audit row |

## Phase 3 — Organization, catalog, assets, workforce

| ID | Task | Needs | Done when |
|---|---|---|---|
| O-1 | Factories (incl. timezone + settings), floors, lines, stations CRUD + `/org/tree` | A-3 | API.md §4 |
| O-2 | `POST /stations/bulk` | O-1 | Creating 200 stations takes one call |
| O-3 | Catalog lists: machine types, brands, defect types, reason codes + seed defaults | A-3 | Each list supports add / edit / deactivate |
| O-4 | Products + operations with SMV | O-3 | Validation: SMV > 0 |
| O-5 | Machines + `machine_assignments` with `EXCLUDE` overlap constraint | O-1, O-3 | Overlapping placement rejected by DB → `409` |
| O-6 | Workers + skills | O-1, O-4 | `rfid_card_id` unique |
| O-7 | `worker_assignments` (+ bulk) with `EXCLUDE` constraint; `at=` lookup | O-5, O-6 | Overlap → `ASSIGNMENT_OVERLAP`; lookup by time correct across reassignment |
| O-8 | Generic CSV import engine: validate all → preview → commit; stores file + result | A-5 | Per-row errors returned; nothing written before commit |
| O-9 | Importers: org, machines, workers, operations, needle batches (table only), production, attendance — per [IMPORT_TEMPLATES.md](IMPORT_TEMPLATES.md) | O-8, O-7 | Each sample file in `docs/import-templates/` imports cleanly |

## Phase 4 — Policies

| ID | Task | Needs | Done when |
|---|---|---|---|
| P-1 | `policies` + `policy_versions`; new version closes the previous one | O-1 | History kept; versions never edited |
| P-2 | Pydantic schema per kind (`shift`, `target`, `thresholds`, `retention`) exposed as JSON Schema | P-1 | `/policies/schema/{kind}` returns the schema the UI renders |
| P-3 | Shift policy validation: cross-midnight, breaks inside shift, overtime limits | P-2 | Unit tests incl. night shift 22:00–06:00 |
| P-4 | `/policies/resolve` (most specific scope wins: station's operation → line → factory) | P-1 | Unit tests for scope precedence |

## Phase 5 — Ingest and events

| ID | Task | Needs | Done when |
|---|---|---|---|
| E-1 | Devices + hashed tokens + rotate; device auth dependency | A-3, O-1 | Token shown once; wrong token → 401 |
| E-2 | `events` table, monthly partitions, auto-create next partition job | C-1 | Insert into a new month works without manual steps |
| E-3 | `POST /ingest/events`: schema validation, attribution (machine, worker, operation, policy at event time), idempotency, per-row results | E-1, E-2, O-7, P-4 | Duplicate UUID → `duplicate`; reassignment mid-shift attributes correctly |
| E-4 | Review status rules (threshold + always-review types) | E-3 | Unit tests |
| E-5 | Heartbeat endpoint + Redis last-seen | E-1 | `/devices/health` shows online/offline |
| E-6 | Review queue + `POST /events/{id}/review` (`event_reviews`, cached status) | E-4 | Raw event unchanged after review; audit row written |
| E-7 | Manual events (downtime reason, pause reason, authorized break) | E-3 | Supervisor can record a pause for a station |
| E-8 | `/stations/{id}/timeline` (worker + machine intervals) | E-6 | Returns merged intervals for a shift date |

## Phase 6 — Simulator

| ID | Task | Needs | Done when |
|---|---|---|---|
| SIM-1 | CLI: N stations, shift policy, speed factor; posts to ingest with device tokens | E-3 | `simulator run --stations 100 --speed 60` fills a shift in ~8 min |
| SIM-2 | Scenarios: normal, long idle, phone use, breakdown, device offline, late events, reassignment | SIM-1 | Each scenario selectable by flag |
| SIM-3 | Golden files: expected shift summaries per scenario | SIM-2, T-2 | Used as regression tests in CI |
| SIM-4 | Demo seed: one factory, 2 floors, 6 lines, 200 stations, workers, operations, policies | O-9, P-3 | `make demo` gives a full demo install |

## Phase 7 — Production and time accounting

| ID | Task | Needs | Done when |
|---|---|---|---|
| T-1 | Production entries: create / edit draft / confirm / stats | O-7 | API.md §12 |
| T-2 | Shift summary engine: minute grid, precedence (PRD §7.1), overtime, coverage, SMV efficiency | E-6, P-3, T-1 | Unit tests incl. night shift, overlap, missing data, reclassified events |
| T-3 | `close_shifts` + `recompute_stale` Celery jobs; late events / reviews mark stale | T-2 | Late event changes summary within 5 min |
| T-4 | Hourly production rollup | T-1 | Line dashboard reads rollups, not raw rows |

## Phase 8 — Alerts and live updates

| ID | Task | Needs | Done when |
|---|---|---|---|
| L-1 | `alert_rules` + seed defaults (long idle, long machine stop, phone use, device offline) | E-3 | Rules editable via API |
| L-2 | Rule evaluator: event-based (on ingest) + metric-based (scheduled) | L-1 | Simulator breakdown scenario raises a machine-stop alert |
| L-3 | Alerts API: list, summary, ack, resolve; notifications per recipient role and scope | L-2 | API.md §17 |
| L-4 | `/alert-rules/{id}/test` dry run over last 7 days | L-2 | Returns count without creating alerts |
| L-5 | Device watchdog → device-offline alert, auto-resolve | E-5, L-2 | Stop simulator device → alert within 3 min; restart → resolved |
| L-6 | SSE `/stream/floor` via Redis pub/sub (station state, alert, alert update) | E-3, L-3 | Browser receives updates < 10 s after ingest |
| L-7 | `/overview` endpoint | T-4, L-3, E-5 | Returns totals + per-line data for 200 stations in < 800 ms |

## Phase 9 — Web app

| ID | Task | Needs | Done when |
|---|---|---|---|
| W-1 | App shell: layout, role-based navigation, `next-intl` en/bn, language switch, API client with envelope + error code translation | S-5, A-2 | Switching language changes all UI text |
| W-2 | Public landing page + login | W-1 | Lighthouse accessibility ≥ 90 |
| W-3 | Generic data table (server paging, filters, sort) + generic form builder from JSON Schema | W-1 | Reused by all config screens |
| W-4 | Admin config: factory structure tree, bulk stations, catalog lists, operations/SMV, machines, workers, devices, users/roles | W-3, O-*, A-4 | Admin can set up a factory from zero without touching the DB |
| W-5 | CSV import wizard (upload → preview errors → commit) | W-3, O-9 | Works for all 7 templates |
| W-6 | Policy editor (form from schema, version history, effective date) | W-3, P-2 | New version visible in history |
| W-7 | Admin overview dashboard (live via SSE) | L-6, L-7 | Station counts, output vs target, alerts, device health update live |
| W-8 | Alert center + alert rule editor (with dry-run) + notification bell | L-3, L-4 | Rule created in UI fires on simulator scenario |
| W-9 | Supervisor: live floor, assignments (single + bulk), production entry, pause/downtime reasons | L-6, O-7, T-1, E-7 | Full shift doable on a 10" tablet |
| W-10 | Station timeline + review queue (confirm / reject / reclassify) | E-6, E-8 | Review updates the shift summary after recompute |
| W-11 | Audit log viewer | A-5 | Filters by user, entity, date |
| W-12 | Apply UI design when available | design upload | Screens match design |

## Phase 10 — Reports

| ID | Task | Needs | Done when |
|---|---|---|---|
| R-1 | Report job framework (queue, MinIO storage, signed download) | C-1 | `POST /reports` → 202 → ready |
| R-2 | Shift report + daily line report (PDF with Bangla font, CSV) | R-1, T-3 | Bangla renders correctly in PDF |
| R-3 | Downtime report | R-1, E-7 | |

## Phase 11 — Release hardening

| ID | Task | Needs | Done when |
|---|---|---|---|
| H-1 | E2E (Playwright): login → setup → assign → simulator shift → review → alert → shift report | all above | Green in CI |
| H-2 | Load test: 500 stations simulated, 1 day | SIM-1 | NFRs in TRD §5 met |
| H-3 | Security pass: RBAC matrix tests, rate limits, headers, dependency audit | A-3 | No critical / high findings |
| H-4 | Backup + restore scripts; restore tested | S-2 | Restore of yesterday's backup works on a clean machine |
| H-5 | Install script + install guide + README | S-2 | A new person installs from the guide alone |
| H-6 | Retention purge job | P-2 | Old evidence/events removed per policy, purge audited |

## R1 definition of done

- [ ] A new factory can be fully configured through the UI or CSV, with any number of stations
- [ ] Simulator runs a full shift for 200+ stations; summaries match golden files
- [ ] Supervisor can run a complete shift on a tablet in English or Bangla
- [ ] Admin overview and alert center update live; alert rules are editable and testable
- [ ] Shift and daily reports export as PDF and CSV
- [ ] Coverage ≥ 80% on backend services; E2E green
- [ ] Backup restore tested; install guide verified
