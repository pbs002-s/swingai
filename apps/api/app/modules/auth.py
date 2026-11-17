"""Login, logout and the current user (docs/API.md §2)."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.db import get_session, utcnow
from app.core.errors import AppError, ok
from app.core.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    client_ip,
    current_session,
    current_user,
    hash_password,
    login_limiter,
    new_token,
    sha256,
    verify_password,
)
from app.models import Session, User

router = APIRouter(prefix="/auth", tags=["auth"])
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=256)


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "locale": user.locale,
        "roles": [{"role": r.role, "scope_type": r.scope_type, "scope_id": r.scope_id} for r in user.roles],
    }


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_session)):
    settings = get_settings()
    login_limiter.check(client_ip(request))
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    now = utcnow()
    locked = bool(user and user.locked_until and user.locked_until > now)
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if user is None or locked or not user.is_active or not valid:
        if user and not locked:
            user.failed_logins += 1
            if user.failed_logins >= settings.max_login_attempts:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_logins = 0
            await db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is wrong.")

    token, csrf = new_token(), new_token()
    user.failed_logins, user.locked_until = 0, None
    db.add(
        Session(
            token_hash=sha256(token),
            user_id=user.id,
            csrf_token=csrf,
            expires_at=now + timedelta(hours=settings.session_ttl_hours),
        )
    )
    audit(db, user.id, "login", "user", user.id, ip=client_ip(request))
    await db.commit()

    max_age = settings.session_ttl_hours * 3600
    common = {"max_age": max_age, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)
    return ok({"user": user_out(user), "csrf_token": csrf})


@router.post("/logout")
async def logout(response: Response, sess: Session = Depends(current_session), db: AsyncSession = Depends(get_session)):
    await db.execute(delete(Session).where(Session.token_hash == sess.token_hash))
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return ok({"logged_out": True})


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return ok(user_out(user))
