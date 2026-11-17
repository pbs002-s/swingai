from sqlalchemy import select

from app.models import User
from app.simulator.seed import DEMO_PASSWORD


async def test_login_sets_httponly_session_and_csrf_cookie(anon):
    r = await anon.post("/auth/login", json={"email": "admin@stitchsense.local", "password": DEMO_PASSWORD})
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("ss_session="))
    assert "HttpOnly" in session and "SameSite=lax" in session
    assert any(c.startswith("ss_csrf=") and "HttpOnly" not in c for c in cookies)
    assert "password_hash" not in r.text


async def test_wrong_password_is_rejected_without_saying_which_part_is_wrong(anon):
    r = await anon.post("/auth/login", json={"email": "admin@stitchsense.local", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r2 = await anon.post("/auth/login", json={"email": "ghost@stitchsense.local", "password": "nope"})
    assert r2.json()["error"]["message"] == r.json()["error"]["message"]


async def test_me_requires_a_session(anon, admin):
    assert (await anon.get("/auth/me")).status_code == 401
    me = (await admin.get("/auth/me")).json()["data"]
    assert {r["role"] for r in me["roles"]} >= {"system_admin", "factory_admin"}


async def test_mutating_request_without_csrf_header_is_refused(admin):
    token = admin.headers.pop("x-csrf-token")
    r = await admin.post("/auth/logout")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"
    admin.headers["x-csrf-token"] = token


async def test_logout_ends_the_session(admin):
    assert (await admin.post("/auth/logout")).status_code == 200
    assert (await admin.get("/auth/me")).status_code == 401


async def test_account_locks_after_repeated_failures(anon, db):
    email = "manager@stitchsense.local"
    for _ in range(10):
        await anon.post("/auth/login", json={"email": email, "password": "wrong"})
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.locked_until is not None
    user.locked_until = None  # unlock for the other tests
    await db.commit()


async def test_login_is_rate_limited_per_client(anon):
    codes = [(await anon.post("/auth/login", json={"email": "x@y.z", "password": "a"})).status_code for _ in range(11)]
    assert codes[-1] == 429
