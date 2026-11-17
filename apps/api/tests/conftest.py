"""Test setup: a real Postgres database (SS_TEST_DATABASE_URL), rebuilt and seeded once per run."""

import os
import secrets
from collections.abc import AsyncIterator

os.environ["SS_ENV"] = "test"
os.environ["SS_LOGIN_RATE_PER_MINUTE"] = "10"  # tests must not inherit a developer's .env
os.environ["SS_SIMULATOR_ENABLED"] = "false"
os.environ["SS_DATABASE_URL"] = os.environ.get(
    "SS_TEST_DATABASE_URL", "postgresql+asyncpg://stitchsense:stitchsense@localhost:5433/stitchsense_test"
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import login_limiter, sha256  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Device  # noqa: E402
from app.simulator.seed import DEMO_PASSWORD, ensure_admin, seed_demo  # noqa: E402

DEVICE_TOKEN = secrets.token_urlsafe(24)


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await ensure_admin(db)
        await seed_demo(db)
        edge = (await db.execute(select(Device).where(Device.code == "EDGE-1"))).scalar_one()
        edge.token_hash = sha256(DEVICE_TOKEN)
        await db.commit()
    yield
    await engine.dispose()


@pytest.fixture
async def db() -> AsyncIterator:
    async with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    login_limiter.hits.clear()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1")


@pytest.fixture
async def anon() -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as c:
        yield c


async def login_as(email: str) -> httpx.AsyncClient:
    c = _client()
    r = await c.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    c.headers["x-csrf-token"] = r.json()["data"]["csrf_token"]
    return c


@pytest.fixture
async def admin() -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("admin@stitchsense.local")
    yield c
    await c.aclose()


@pytest.fixture
async def supervisor() -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("supervisor@stitchsense.local")
    yield c
    await c.aclose()


@pytest.fixture
async def manager() -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("manager@stitchsense.local")
    yield c
    await c.aclose()


@pytest.fixture
async def device() -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as c:
        c.headers["authorization"] = f"Bearer {DEVICE_TOKEN}"
        yield c
