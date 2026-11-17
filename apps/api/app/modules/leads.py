"""Public site-survey requests from the landing page."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ok
from app.core.security import RateLimiter, client_ip
from app.models import Lead

router = APIRouter(tags=["leads"])
lead_limiter = RateLimiter(limit=5, window_s=600)


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    company: str = Field(min_length=2, max_length=160)
    stations: Literal["under_100", "100_500", "over_500"]
    website: str = Field(default="", max_length=0)  # honeypot: humans leave it empty


@router.post("/leads", status_code=201)
async def create_lead(body: LeadIn, request: Request, db: AsyncSession = Depends(get_session)):
    ip = client_ip(request)
    lead_limiter.check(ip)
    db.add(
        Lead(
            name=body.name.strip(), email=body.email.strip().lower(), company=body.company.strip(), stations=body.stations, ip=ip
        )
    )
    await db.commit()
    return ok({"received": True})
