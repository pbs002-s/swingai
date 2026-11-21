"""Load test: push events like an edge box would, then time the dashboard queries (TRD section 5, task H-2).

    uv run python tools/loadtest.py --base http://localhost:8000 --device-token <token> \
        --email admin@stitchsense.local --password <pw> --events 100000

Run it against a TEST install: it writes real events. The device token comes from POST /devices/{id}/rotate-token.
Prints throughput, latency percentiles and whether each target from the TRD was met.
"""

import argparse
import asyncio
import collections
import random
import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

STATES = ("working", "idle", "away")
P95_DASHBOARD_MS = 800  # TRD: dashboard queries P95 <= 800 ms


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))] if ordered else 0.0


async def login(client: httpx.AsyncClient, email: str, password: str) -> None:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    client.headers["x-csrf-token"] = r.json()["data"]["csrf_token"]


def make_events(codes: list[str], n: int) -> list[dict]:
    start = datetime.now(UTC) - timedelta(hours=8)
    return [
        {
            "event_uuid": str(uuid.uuid4()),
            "event_type": "worker_state",
            "state": random.choice(STATES),  # noqa: S311 - test data, not security
            "station_code": random.choice(codes),  # noqa: S311
            "start_time": (start + timedelta(seconds=i * 8 * 3600 / n)).isoformat(),
            "confidence": 0.9,
        }
        for i in range(n)
    ]


async def push(
    base: str, token: str, events: list[dict], batch: int, concurrency: int
) -> tuple[list[float], collections.Counter, float]:
    latencies: list[float] = []
    rejected: collections.Counter = collections.Counter()
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=base, headers={"authorization": f"Bearer {token}"}, timeout=60) as c:

        async def one(chunk: list[dict]) -> None:
            async with sem:
                t0 = time.perf_counter()
                r = await c.post("/api/v1/ingest/events", json={"events": chunk})
                latencies.append((time.perf_counter() - t0) * 1000)
                if r.status_code != 200:
                    rejected[f"HTTP {r.status_code}"] += len(chunk)
                else:
                    rejected.update(x["error"] for x in r.json()["data"]["results"] if x["error"])

        t0 = time.perf_counter()
        await asyncio.gather(*(one(events[i : i + batch]) for i in range(0, len(events), batch)))
        return latencies, rejected, time.perf_counter() - t0


async def dashboards(client: httpx.AsyncClient, repeats: int) -> dict[str, list[float]]:
    tree = (await client.get("/api/v1/org/tree")).json()["data"]
    lines = [ln["id"] for f in tree for fl in f["floors"] for ln in fl["lines"]]
    paths = {"overview": "/api/v1/overview", "performance": "/api/v1/performance", "floor": f"/api/v1/floor?line_id={lines[0]}"}
    out: dict[str, list[float]] = {k: [] for k in paths}
    for _ in range(repeats):
        for name, path in paths.items():
            t0 = time.perf_counter()
            r = await client.get(path)
            r.raise_for_status()
            out[name].append((time.perf_counter() - t0) * 1000)
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--device-token", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--events", type=int, default=50_000)
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=20)
    a = ap.parse_args()

    async with httpx.AsyncClient(base_url=a.base, timeout=60) as admin:
        await login(admin, a.email, a.password)
        tree = (await admin.get("/api/v1/org/tree")).json()["data"]
        lines = [ln for f in tree for fl in f["floors"] for ln in fl["lines"]]
        floor = (await admin.get(f"/api/v1/floor?line_id={lines[0]['id']}")).json()["data"]
        codes = [s["code"] for s in floor["stations"]] if "stations" in floor else []
        stations = sum(ln["stations"] for ln in lines)
        print(f"{stations} stations on {len(lines)} lines; sending {a.events} events in batches of {a.batch}")
        if not codes:
            raise SystemExit("could not read station codes from /floor")

        lat, rejected, secs = await push(a.base, a.device_token, make_events(codes, a.events), a.batch, a.concurrency)
        print(f"ingest: {a.events / secs:,.0f} events/s, {len(lat)} requests, rejected {sum(rejected.values())} {dict(rejected)}")
        print(f"  request latency ms: p50 {statistics.median(lat):.0f}  p95 {pct(lat, 0.95):.0f}  p99 {pct(lat, 0.99):.0f}")

        dash = await dashboards(admin, a.repeats)
        ok = True
        for name, vals in dash.items():
            p95 = pct(vals, 0.95)
            met = p95 <= P95_DASHBOARD_MS
            ok &= met
            print(f"{name}: p50 {statistics.median(vals):.0f} ms  p95 {p95:.0f} ms  {'ok' if met else 'ABOVE TARGET'}")
    return 0 if ok and not rejected else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
