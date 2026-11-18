"""StitchSense API application."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.errors import install_error_handlers, ok
from app.core.security import require_roles
from app.models import User
from app.modules import (
    alerts,
    auth,
    cameras,
    edge_sim,
    events,
    floor,
    imports,
    ingest,
    leads,
    needles,
    org,
    performance,
    setup,
    setup_users,
    stream,
)
from app.simulator.engine import Simulator
from app.simulator.seed import ensure_admin, seed_demo

log = logging.getLogger("stitchsense")


async def _rules_loop(interval: float) -> None:
    while True:
        try:
            async with SessionLocal() as db:
                await alerts.evaluate_rules(db)
                await edge_sim.run_simulated_edge_jobs(db)
        except Exception:
            log.exception("alert rule evaluation failed")
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    simulator = Simulator(SessionLocal)
    app.state.simulator = simulator
    tasks: list[asyncio.Task[None]] = []
    if settings.env != "test":
        async with SessionLocal() as db:
            await ensure_admin(db)
            if settings.seed_demo and settings.env != "production" and await seed_demo(db):
                log.info("seeded the demo factory")
        tasks.append(asyncio.create_task(_rules_loop(settings.rules_interval_seconds), name="alert-rules"))
        if settings.simulator_enabled:
            simulator.start()
    yield
    await simulator.stop()
    for t in tasks:
        t.cancel()
    await engine.dispose()


health = APIRouter(tags=["ops"])


@health.get("/healthz")
async def healthz():
    return ok({"status": "ok"})


@health.get("/readyz")
async def readyz():
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    return ok({"database": "ok"})


sim_router = APIRouter(prefix="/simulator", tags=["simulator"])


class SimIn(BaseModel):
    running: bool


@sim_router.get("")
async def sim_status(request: Request, _: User = Depends(require_roles("factory_admin"))):
    return ok({"running": request.app.state.simulator.running})


@sim_router.post("")
async def sim_control(body: SimIn, request: Request, _: User = Depends(require_roles("factory_admin"))):
    sim: Simulator = request.app.state.simulator
    if body.running:
        sim.start()
    else:
        await sim.stop()
    return ok({"running": sim.running})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="StitchSense API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.env == "production" else "/api/docs",
        openapi_url=None if settings.env == "production" else "/api/openapi.json",
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    api = APIRouter(prefix="/api/v1")
    for r in (
        health,
        auth.router,
        org.router,
        ingest.router,
        events.router,
        floor.router,
        alerts.router,
        needles.router,
        leads.router,
        performance.router,
        cameras.router,
        setup.router,
        setup_users.router,
        imports.router,
        stream.router,
        sim_router,
    ):
        api.include_router(r)
    app.include_router(api)
    return app


app = create_app()
