"""Server-Sent Events for the live floor and alerts (docs/API.md §11).

The stream checks the session itself with short-lived DB sessions, so no database connection is held
while it is open, and it ends within one heartbeat after logout or session expiry.
"""

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core import bus
from app.core.db import SessionLocal, utcnow
from app.core.errors import AppError
from app.core.security import SESSION_COOKIE, sha256
from app.models import Session

router = APIRouter(tags=["stream"])
HEARTBEAT_S = 15
MAX_STREAMS_PER_USER = 4
_open: dict[int, int] = defaultdict(int)


async def _session_user(token: str | None) -> int | None:
    if not token:
        return None
    async with SessionLocal() as db:
        sess = await db.get(Session, sha256(token))
        return sess.user_id if sess and sess.expires_at > utcnow() else None


@router.get("/stream/floor")
async def stream_floor(request: Request, line_id: int | None = None):
    token = request.cookies.get(SESSION_COOKIE)
    user_id = await _session_user(token)
    if user_id is None:
        raise AppError(401, "UNAUTHENTICATED", "Log in to continue.")
    if _open[user_id] >= MAX_STREAMS_PER_USER:
        raise AppError(429, "RATE_LIMITED", "Too many live connections. Close another tab.")
    _open[user_id] += 1

    async def events() -> AsyncIterator[str]:
        q = bus.subscribe()
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)
                except TimeoutError:
                    if await _session_user(token) != user_id:
                        return  # logged out or expired: end the stream
                    yield ": keep-alive\n\n"
                    continue
                data = msg["data"]
                if line_id and msg["kind"] == "station_state" and data.get("line_id") != line_id:
                    continue
                yield f"event: {msg['kind']}\ndata: {json.dumps(data, default=str)}\n\n"
        finally:
            bus.unsubscribe(q)
            _open[user_id] -= 1

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
