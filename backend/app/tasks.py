"""Background task spawner that never swallows exceptions silently."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

log = logging.getLogger("tasks")

_running: set[asyncio.Task] = set()


def spawn(coro: Coroutine[Any, Any, Any], name: str = "") -> asyncio.Task:
    task = asyncio.create_task(coro, name=name or coro.__qualname__)
    _running.add(task)

    def _done(t: asyncio.Task) -> None:
        _running.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log.error("background task %s failed", t.get_name(), exc_info=t.exception())

    task.add_done_callback(_done)
    return task
