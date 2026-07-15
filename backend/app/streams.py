"""In-process pub/sub bridging the sim loop and agent runs to SSE clients."""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator


def _default(o: Any):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


class Broadcaster:
    def __init__(self) -> None:
        # FastAPI executes regular ``def`` endpoints in worker threads. Those
        # endpoints publish control/action events too, and asyncio.Queue is not
        # thread-safe. Remember the owning loop for every subscriber so a
        # worker-thread publication can wake it through call_soon_threadsafe.
        self._subscribers: dict[
            asyncio.Queue[tuple[str, str]], asyncio.AbstractEventLoop
        ] = {}
        self._lock = threading.Lock()

    def _enqueue(
        self, q: asyncio.Queue[tuple[str, str]], event: str, payload: str
    ) -> None:
        with self._lock:
            if q not in self._subscribers:
                return
        try:
            q.put_nowait((event, payload))
        except asyncio.QueueFull:
            # A slow browser should not be left connected to a queue that was
            # silently removed forever. Keep the newest state flowing; the
            # REST invalidations and authoritative tick/positions events make
            # the client converge again.
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            q.put_nowait((event, payload))

    def publish(self, event: str, data: dict) -> None:
        payload = json.dumps(data, default=_default)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        with self._lock:
            subscribers = list(self._subscribers.items())
        for q, loop in subscribers:
            if loop.is_closed():
                with self._lock:
                    self._subscribers.pop(q, None)
            elif current_loop is loop:
                self._enqueue(q, event, payload)
            else:
                try:
                    loop.call_soon_threadsafe(self._enqueue, q, event, payload)
                except RuntimeError:  # loop closed between the check and call
                    with self._lock:
                        self._subscribers.pop(q, None)

    @asynccontextmanager
    async def subscribe(
        self,
    ) -> AsyncIterator[asyncio.Queue[tuple[str, str]]]:
        """Register before taking an initial REST/DB snapshot.

        Registering first closes the gap where a control/action event could be
        published after the snapshot but before the SSE generator started
        consuming the broadcaster.
        """
        q: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=500)
        with self._lock:
            self._subscribers[q] = asyncio.get_running_loop()
        try:
            yield q
        finally:
            with self._lock:
                self._subscribers.pop(q, None)

    async def stream(self) -> AsyncIterator[tuple[str, str]]:
        async with self.subscribe() as q:
            while True:
                yield await q.get()


broadcaster = Broadcaster()
