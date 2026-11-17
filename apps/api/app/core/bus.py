"""In-process publish/subscribe for live updates (Server-Sent Events).

ponytail: single process only; swap for Redis pub/sub when the API runs as several processes.
"""

import asyncio
from typing import Any

_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[dict[str, Any]]) -> None:
    _subscribers.discard(q)


def publish(kind: str, data: dict[str, Any]) -> None:
    message = {"kind": kind, "data": data}
    for q in list(_subscribers):
        if q.full():  # a slow client loses old updates rather than blocking everyone
            q.get_nowait()
        q.put_nowait(message)
