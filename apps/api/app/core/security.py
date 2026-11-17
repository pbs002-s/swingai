"""Password hashing, tokens, and request dependencies for users and devices."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session, utcnow
from app.core.errors import AppError
from app.models import Device, Session, User

SESSION_COOKIE = "ss_session"
CSRF_COOKIE = "ss_csrf"
_hasher = PasswordHasher()
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class RateLimiter:
    """Sliding-window limiter keyed by client.

    ponytail: per-process memory; move to Redis when the API runs more than one process.
    """

    def __init__(self, limit: int, window_s: float):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self.hits.pop(key, None)
            q = self.hits[key]
        if len(q) >= self.limit:
            raise AppError(429, "RATE_LIMITED", "Too many attempts. Wait a minute and try again.")
        q.append(now)


login_limiter = RateLimiter(limit=get_settings().login_rate_per_minute, window_s=60)
ingest_limiter = RateLimiter(limit=120, window_s=60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def current_session(request: Request, db: AsyncSession = Depends(get_session)) -> Session:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AppError(401, "UNAUTHENTICATED", "Log in to continue.")
    sess = await db.get(Session, sha256(token))
    if sess is None or sess.expires_at <= utcnow():
        raise AppError(401, "UNAUTHENTICATED", "Your session has ended. Log in again.")
    if request.method in _MUTATING:
        sent = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(sent, sess.csrf_token):
            raise AppError(403, "CSRF_FAILED", "The page is out of date. Reload and try again.")
    return sess


async def current_user(sess: Session = Depends(current_session), db: AsyncSession = Depends(get_session)) -> User:
    user = await db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHENTICATED", "Log in to continue.")
    return user


def require_roles(*roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Allow the request if the user holds any of `roles` (system_admin always passes)."""

    async def _dep(user: User = Depends(current_user)) -> User:
        held = {r.role for r in user.roles}
        if "system_admin" in held or held.intersection(roles):
            return user
        raise AppError(403, "FORBIDDEN", "Your role cannot do this.")

    return _dep


def check_line_scope(user: User, line_id: int) -> None:
    """Roles scoped to a line only act on that line; roles scoped to all/factory act everywhere."""
    if any(r.role == "system_admin" or r.scope_type in ("all", "factory") for r in user.roles):
        return
    if any(r.scope_type == "line" and r.scope_id == line_id for r in user.roles):
        return
    raise AppError(403, "FORBIDDEN", "This line is outside your access.")


async def current_device(request: Request, db: AsyncSession = Depends(get_session)) -> Device:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise AppError(401, "DEVICE_UNKNOWN", "Device token missing.")
    device = (await db.execute(select(Device).where(Device.token_hash == sha256(auth[7:].strip())))).scalar_one_or_none()
    if device is None or not device.is_active:
        raise AppError(401, "DEVICE_UNKNOWN", "Device token not recognised.")
    ingest_limiter.check(device.code)
    return device
