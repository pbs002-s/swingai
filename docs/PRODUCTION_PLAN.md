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

Built and tested:

- [x] CI green on the live camera / roles / lab PR (#2)
- [x] 1 Privacy zones masked on the edge before streaming, audio dropped, wall warns when no mask is set. Tested with unit tests; **not tested with a real go2rtc, ffmpeg or camera**
- [~] 2 Live view access: the player and its registration API are password-protected. Short-lived signed links are **not built**
- [x] 3 Backup and restore scripts. Tested on a copy of the dev database (backup, verify, replace, corrupt-dump refusal)
- [x] 4 Day reports per line: JSON, CSV, print to PDF. **No server-side PDF.** Downtime and worker sections
- [x] 5 Audit log viewer
- [x] 6 Policies: versioned shift, thresholds, retention, with editor and scheduling
- [x] 7 Alert rule dry run over the last 7 days
- [x] 8 Retention purge, scheduled and audited
- [x] 10 Request ID in logs and headers, Bangla error messages. **Optimistic locking (C-4) is not built**
- [x] 11 Install guide, env generator, health check script. Not tested on a clean machine or with a real domain
- [x] 14 E2E tests run in CI and pass (PR #3). Real bugs they found and are fixed: sidebar cut off on short screens, saved message vanishing on the policies page, lab blocked by the production CSP. The web build retries when the Google Fonts download fails

Not done:

- [ ] 2 Signed, short-lived live links
- [ ] 9 Scheduled jobs "close shifts / recompute stale": by design nothing is cached, summaries are computed from events on demand, so there is nothing to recompute. T-3 is not needed in this architecture
- [~] 12 Load test: script and a first measurement are done ([LOAD_TEST.md](LOAD_TEST.md)). Dashboards and ingest meet the targets at 159 stations; **the performance ranking does not** (p95 1.6 s vs 0.8 s) and needs rollups (T-4). Not run at 500 stations or on a server
- [ ] T-4 Hourly/daily rollups so the ranking stays fast at real data volume
- [ ] 13 Monitoring beyond `healthcheck.sh` (no edge-box-offline notification outside the in-app alert, no disk alerts on the edge box)
- [ ] Face blur on live video (needs a per-frame detector on the edge box)
- [ ] C-4 optimistic locking
- [ ] Management approval of bonus and training recommendations (feature does not exist)
