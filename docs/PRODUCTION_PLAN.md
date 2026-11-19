# Production readiness plan

Status: 2026-11-19. Closes the gaps between `docs/TASKS_R1.md` and the code, in the order a client pilot needs them.
Tick a box only when the item is built, tested and merged.

## Order and why

| # | Item | Task IDs | Why first |
|---|---|---|---|
| 1 | Live view privacy: privacy zones masked on the edge before streaming | VISION plan §6 | Breaks the project's privacy rule today |
| 2 | Live view access: short-lived signed links, checked at the edge | TRD §security | Anyone on the LAN with the URL can watch |
| 3 | Backup and restore scripts, restore tested | H-4 | Biggest data-loss risk |
| 4 | Reports: shift, daily line, downtime. CSV, and PDF by browser print (Bangla renders correctly) | R-1 to R-3 | R1 exit criterion |
| 5 | Audit log viewer | W-11 | Audit rows exist, nobody can read them |
| 6 | Policy versions API and editor (shift, thresholds, targets, retention) | P-2 to P-4, W-6 | Policies are only editable by SQL today |
| 7 | Alert rule dry run | L-4 | Rules cannot be tested before saving |
| 8 | Retention purge job (audited) | H-6 | Privacy notice promises limits |
| 9 | Scheduled jobs: close shifts, recompute stale summaries | T-3 | Late events change summaries |
| 10 | Request ID in logs, Bangla error messages, optimistic locking | C-2 to C-4 | Operability |
| 11 | Install script and guide, tested on a clean machine | H-5 | A new person installs alone |
| 12 | Load test, 500 stations | H-2 | NFRs in TRD §5 |
| 13 | Monitoring: health check, edge box offline alert, disk | – | Nobody watches the install |
| 14 | E2E in CI green, tests independent of leftover data | H-1 | CI e2e is skipped today |

## Decisions

- **Masking:** privacy zones are filled black on the edge box with ffmpeg before go2rtc serves the stream. Polygons are reduced to their bounding boxes, which can only hide more, never less. Face blur on live video needs a per-frame detector and is not part of this step: until it exists, cameras with `face_blur` and no privacy zone show a warning on the live wall.
- **Signed access:** the API issues a link valid for 5 minutes; the edge proxy checks it against the API. Video still never passes through the central server.
- **PDF:** browsers print Bangla correctly; server-side PDF needs Indic shaping libraries that are heavy to install on client machines. Reports are HTML pages with a print stylesheet, plus CSV.
- **Jobs:** stay in-process (project decision), no Celery or Redis.

## Out of scope here (later releases)

R2 sensors, R3 trained vision model and needle detection from video, R4 quality analytics, management approval of bonus and training recommendations.

## Progress

- [x] CI green on the live camera / roles / lab PR
- [ ] 1 to 14 above
