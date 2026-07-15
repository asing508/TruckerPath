"""The event gate between deterministic monitoring and generative AI.

Detection, dedupe, and prioritization are free (pure Python over telemetry).
The LLM wakes up only when a human asks, or when a unique CRITICAL incident
passes this gate with auto-investigate enabled.

The budget meters what Google meters: individual Gemini requests, counted at
the moment each HTTP call is made (tool-loop steps, finalization, vision -
everything). Spend persists in SQLite per quota day in America/Los_Angeles,
matching Google's daily reset, so neither a server restart nor a demo reset
mints fresh budget. A workflow may not start unless a reserve of requests
remains, so runs are refused up front instead of dying halfway.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from ..config import (
    AI_AUTO_INVESTIGATE_DEFAULT,
    AI_AUTO_MIN_GAP_S,
    AI_DAILY_REQUEST_BUDGET,
    AI_RUN_RESERVE_REQUESTS,
)
from ..db import engine as db_engine
from ..models import AiSpend
from ..streams import broadcaster

log = logging.getLogger("agents.budget")

try:
    from zoneinfo import ZoneInfo

    _QUOTA_TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # no tz database on this host; fixed PST is close enough
    _QUOTA_TZ = timezone(timedelta(hours=-8))


def quota_day() -> str:
    return datetime.now(_QUOTA_TZ).date().isoformat()


class AiBudget:
    def __init__(
        self,
        request_cap: int | None = None,
        run_reserve: int | None = None,
        auto_enabled: bool | None = None,
        auto_min_gap_s: int | None = None,
    ) -> None:
        self.request_cap = request_cap if request_cap is not None else AI_DAILY_REQUEST_BUDGET
        self.run_reserve = run_reserve if run_reserve is not None else AI_RUN_RESERVE_REQUESTS
        self.auto_enabled = auto_enabled if auto_enabled is not None else AI_AUTO_INVESTIGATE_DEFAULT
        self.auto_min_gap_s = auto_min_gap_s if auto_min_gap_s is not None else AI_AUTO_MIN_GAP_S
        self._lock = threading.Lock()
        self._day: str | None = None  # lazy: DB may not exist at import time
        self._used = 0
        self._last_auto = 0.0

    def _sync(self) -> None:
        """Load today's spend from SQLite on first use and on day rollover."""
        day = quota_day()
        if day == self._day:
            return
        with Session(db_engine) as s:
            row = s.get(AiSpend, day)
            self._used = row.requests if row else 0
        self._day = day

    def _persist(self) -> None:
        with Session(db_engine) as s:
            row = s.get(AiSpend, self._day) or AiSpend(day=self._day, requests=0)
            row.requests = self._used
            s.add(row)
            s.commit()

    def status(self) -> dict:
        with self._lock:
            self._sync()
            return {
                "auto_enabled": self.auto_enabled,
                "used": self._used,
                "cap": self.request_cap,
                "remaining": max(0, self.request_cap - self._used),
            }

    def publish(self) -> None:
        broadcaster.publish("ai_status", self.status())

    def spend_request(self) -> bool:
        """Debit one actual Gemini request. Called by the client wrapper at
        the moment of each HTTP call, so the counter means what Google's
        does. Returns False when the day's cap is spent."""
        with self._lock:
            self._sync()
            if self._used >= self.request_cap:
                return False
            self._used += 1
            self._persist()
        self.publish()
        return True

    def try_start_run(self, kind: str) -> bool:
        """Admission control for a whole workflow: refuse to start unless a
        reserve of requests remains (a tool-loop run makes up to ~11 calls),
        so runs fail at the door instead of mid-investigation."""
        with self._lock:
            self._sync()
            remaining = self.request_cap - self._used
        if remaining < self.run_reserve:
            log.warning("AI budget too low for a %s run (%d requests left, "
                        "reserve %d)", kind, max(0, remaining), self.run_reserve)
            broadcaster.publish("ai_denied", {
                "kind": kind,
                "reason": (f"only {max(0, remaining)} of {self.request_cap} daily "
                           f"Gemini requests left - not enough for a full run"),
            })
            return False
        return True

    def allow_auto(self) -> bool:
        """Extra gate for watchdog-initiated runs: the toggle (default off)
        and an hourly cap, on top of the run reserve."""
        if not self.auto_enabled:
            return False
        with self._lock:
            self._sync()
            if self.request_cap - self._used < self.run_reserve:
                return False
            now = time.monotonic()
            if now - self._last_auto < self.auto_min_gap_s:
                return False
            self._last_auto = now
        return True

    def set_auto(self, enabled: bool) -> dict:
        self.auto_enabled = enabled
        self.publish()
        return self.status()


ai_budget = AiBudget()
