"""Staff accounts and roles (docs/API.md §3). System admin only; password hashes never leave the server."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import get_session
from app.core.errors import AppError, not_found, ok
from app.core.security import client_ip, hash_password, require_roles
from app.models import Factory, Line, Session, User, UserRole
from app.models.auth import ROLES
from app.modules.setup import flush

router = APIRouter(tags=["setup"])
sysadmin = require_roles("system_admin")

Password = Annotated[str, Field(min_length=12, max_length=256)]


class RoleIn(BaseModel):
    role: str
    scope_type: Literal["all", "factory", "line"] = "all"
    scope_id: int | None = None

    @field_validator("role")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"Unknown role. Use one of: {', '.join(ROLES)}")
        return v

    @model_validator(mode="after")
    def _scope(self) -> "RoleIn":
        if (self.scope_type == "all") != (self.scope_id is None):
            raise ValueError("scope_id is required for factory/line scope and must be empty for 'all'")
        return self


class UserIn(BaseModel):
    email: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    ]
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    password: Password
    locale: Literal["en", "bn"] = "en"
    roles: list[RoleIn] = Field(min_length=1, max_length=20)


class UserPatch(BaseModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    is_active: bool | None = None
    locale: Literal["en", "bn"] | None = None


class PasswordIn(BaseModel):
    password: Password


def user_out(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "locale": u.locale,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "roles": [{"role": r.role, "scope_type": r.scope_type, "scope_id": r.scope_id} for r in u.roles],
    }


async def _roles(db: AsyncSession, roles: list[RoleIn]) -> list[UserRole]:
    for r in roles:
        if r.scope_type != "all" and await db.get(Factory if r.scope_type == "factory" else Line, r.scope_id) is None:
            raise not_found(f"{r.scope_type.capitalize()} {r.scope_id}")
    return [UserRole(**r.model_dump()) for r in roles]


async def _user(db: AsyncSession, user_id: int) -> User:
    u = await db.get(User, user_id)
    if u is None:
        raise not_found("User")
    return u


@router.get("/users")
async def users(
    q: str | None = Query(None, max_length=60),
    db: AsyncSession = Depends(get_session),
    _: User = Depends(sysadmin),
):
    stmt = select(User).order_by(User.email).limit(500)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    return ok([user_out(u) for u in (await db.execute(stmt)).scalars()])


@router.post("/users", status_code=201)
async def create_user(body: UserIn, request: Request, db: AsyncSession = Depends(get_session), me: User = Depends(sysadmin)):
    u = User(email=body.email, full_name=body.full_name, locale=body.locale, password_hash=hash_password(body.password))
    u.roles = await _roles(db, body.roles)
    db.add(u)
    await flush(db)
    audit(db, me.id, "user.create", "user", u.id, body.model_dump(mode="json", exclude={"password"}), client_ip(request))
    await db.commit()
    return ok(user_out(u))


@router.patch("/users/{user_id}")
async def edit_user(
    user_id: int, body: UserPatch, request: Request, db: AsyncSession = Depends(get_session), me: User = Depends(sysadmin)
):
    u = await _user(db, user_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if u.id == me.id and data.get("is_active") is False:
        raise AppError(422, "SELF_LOCKOUT", "You cannot deactivate your own account.")
    for k, v in data.items():
        setattr(u, k, v)
    if data.get("is_active") is False:
        await db.execute(delete(Session).where(Session.user_id == u.id))
    audit(db, me.id, "user.update", "user", u.id, data, client_ip(request))
    await db.commit()
    return ok(user_out(u))


@router.put("/users/{user_id}/roles")
async def set_roles(
    user_id: int,
    request: Request,
    body: list[RoleIn] = Body(min_length=1, max_length=20),
    db: AsyncSession = Depends(get_session),
    me: User = Depends(sysadmin),
):
    u = await _user(db, user_id)
    if u.id == me.id and not any(r.role == "system_admin" for r in body):
        raise AppError(422, "SELF_LOCKOUT", "You cannot remove your own system admin role.")
    u.roles = await _roles(db, body)
    audit(db, me.id, "user.roles", "user", u.id, {"roles": [r.model_dump() for r in body]}, client_ip(request))
    await db.commit()
    return ok(user_out(u))


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int, body: PasswordIn, request: Request, db: AsyncSession = Depends(get_session), me: User = Depends(sysadmin)
):
    u = await _user(db, user_id)
    u.password_hash = hash_password(body.password)
    u.failed_logins, u.locked_until = 0, None
    await db.execute(delete(Session).where(Session.user_id == u.id))  # log the user out everywhere
    audit(db, me.id, "user.reset_password", "user", u.id, None, client_ip(request))
    await db.commit()
    return ok({"id": u.id, "reset": True})
