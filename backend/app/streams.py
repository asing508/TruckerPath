"""In-process pub/sub bridging the sim loop and agent runs to SSE clients."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncIterator


def _default(o: Any):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, event: str, data: dict) -> None:
        payload = json.dumps(data, default=_default)
        for q in list(self._subscribers):
            try:
                q.put_nowait((event, payload))
            except asyncio.QueueFull:
                self._subscribers.discard(q)

    async def stream(self) -> AsyncIterator[tuple[str, str]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)


broadcaster = Broadcaster()
