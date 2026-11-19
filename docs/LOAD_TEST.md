# Load test results

Task H-2 (TRD §5). Script: [apps/api/tools/loadtest.py](../apps/api/tools/loadtest.py). Run it against a test install only: it writes real events.

```bash
# on the server under test, raise the per-device request limit (default 120 per minute):  SS_INGEST_RATE_PER_MINUTE=1000000
# use an edge-box device token: a per-station sensor token can only report its own station
cd apps/api && uv run python tools/loadtest.py --device-token <token> --email <admin> --password <pw> --events 100000
```

## What was measured (2026-11-19)

| | |
|---|---|
| Machine | a development laptop (Windows), one `uvicorn` process, PostgreSQL 16 in Docker on the same machine |
| Data | 159 stations on 11 lines; about 139,000 events spread over 3 days (the 100,000 events of this run, plus earlier demo data) |
| **Not measured** | 500 stations, 12 months of data, a Linux server, several API workers |

| Result | Measured | Target (TRD §5) |
|---|---|---|
| Ingest throughput, 8 parallel clients, batches of 100 | **462 events/s**, 0 rejected | about 2 events/s average at 5M events/month, so roughly 200 times the average need |
| Ingest request latency (100 events) | p50 1.65 s, p95 2.3 s | not specified |
| `/overview` | p50 59 ms, p95 85 ms | P95 ≤ 800 ms: **met** |
| `/floor` (one line) | p50 38 ms, p95 54 ms | P95 ≤ 800 ms: **met** |
| `/performance` (7 days, all workers) | p50 920 ms, p95 1,593 ms | P95 ≤ 800 ms: **NOT met** |

## What this means

1. **Ingest is not the bottleneck.** Real edge boxes send changes, not a stream, and one box covers a floor.
2. **The performance ranking will not meet its target at real volume.** It reads raw events for the whole period and works out every worker's time states each time it is asked, so its cost grows with the number of events in the window. 139,000 events already cost 0.9 s. A real install (about 170,000 events a day) over a 7-day window would hold about 1.2 million events; this is an estimate from the measured trend, not a measurement. The fix is the hourly or daily rollup table the task list calls T-4, which does not exist yet: compute each shift day once, store it, and have the ranking read the stored days. Until then, keep the ranking period short on big installs.
3. **A bad request limit can look like an outage.** The first run was rejected 99.5% of the time because of the default limit of 120 requests a minute per device. That limit protects the server and is now the setting `SS_INGEST_RATE_PER_MINUTE`.

## To do before claiming H-2 is done

- Re-run on a Linux server with realistic hardware and 500 stations.
- Build the rollups (T-4), then re-measure `/performance`.
- Measure with 12 months of events (the TRD target) rather than 3 days.
