"""FMCSA property-carrying Hours-of-Service arithmetic over duty intervals.

Rules implemented (49 CFR 395.3):
  - 11h driving limit inside a 14h on-duty window that starts at the first
    on-duty/driving after >= 10h consecutive off-duty/sleeper
  - 30-minute break required after 8h cumulative driving without one
  - 70h on-duty ceiling over a rolling 8-day span, reset by a 34h restart

All computations are pure functions over (events, now) so the ledger can be
re-evaluated at any simulated instant and unit-tested exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import (
    HOS_BREAK_AFTER_DRIVE_MIN,
    HOS_BREAK_MIN,
    HOS_CYCLE_DAYS,
    HOS_CYCLE_LIMIT_MIN,
    HOS_DRIVE_LIMIT_MIN,
    HOS_RESTART_OFF_MIN,
    HOS_WINDOW_LIMIT_MIN,
)
from ..models import DriverDuty, HosEvent

REST_DUTIES = (DriverDuty.OFF, DriverDuty.SLEEPER)
WORK_DUTIES = (DriverDuty.DRIVING, DriverDuty.ON_DUTY)
DAILY_RESET_OFF_MIN = 10 * 60


@dataclass
class HosClocks:
    drive_min_used: int
    window_min_used: int
    cycle_min_used: int
    min_since_break: int
    drive_min_remaining: int
    window_min_remaining: int
    cycle_min_remaining: int
    break_due_in_min: int
    violations: list[str]

    @property
    def worst_remaining_min(self) -> int:
        return min(self.drive_min_remaining, self.window_min_remaining,
                   self.cycle_min_remaining)


def _clip(events: list[HosEvent], now: datetime) -> list[tuple[DriverDuty, datetime, datetime]]:
    out = []
    for e in sorted(events, key=lambda e: e.start):
        end = e.end or now
        if end > now:
            end = now
        if e.start < end:
            out.append((e.duty, e.start, end))
    return out


def _rest_gaps(intervals, horizon_start: datetime, now: datetime):
    """Yield (start, end) spans with no WORK duty, including implicit gaps."""
    work = [(s, e) for d, s, e in intervals if d in WORK_DUTIES and e > horizon_start]
    if not work:
        yield (horizon_start, now)
        return
    work.sort()
    cursor = horizon_start
    for s, e in work:
        if s > cursor:
            yield (cursor, s)
        cursor = max(cursor, e)
    if cursor < now:
        yield (cursor, now)


def compute_clocks(events: list[HosEvent], now: datetime) -> HosClocks:
    intervals = _clip(events, now)
    horizon = now - timedelta(days=HOS_CYCLE_DAYS)

    # --- 14h window start: first work after the latest >=10h rest gap --------
    window_start: datetime | None = None
    last_reset_end: datetime | None = None
    for gs, ge in _rest_gaps(intervals, horizon, now):
        if (ge - gs) >= timedelta(minutes=DAILY_RESET_OFF_MIN):
            last_reset_end = ge
    if last_reset_end is not None and last_reset_end >= now:
        window_start = None  # currently inside a qualifying rest
    else:
        anchor = last_reset_end or horizon
        starts = [s for d, s, e in intervals if d in WORK_DUTIES and e > anchor]
        if starts:
            window_start = max(min(starts), anchor)

    def overlap_min(duties, since: datetime) -> int:
        total = timedelta()
        for d, s, e in intervals:
            if d in duties and e > since:
                total += e - max(s, since)
        return int(total.total_seconds() // 60)

    if window_start is None:
        drive_used = 0
        window_used = 0
    else:
        drive_used = overlap_min((DriverDuty.DRIVING,), window_start)
        window_used = int((now - window_start).total_seconds() // 60)

    # --- 70h/8d cycle, honoring a 34h restart ---------------------------------
    cycle_anchor = horizon
    for gs, ge in _rest_gaps(intervals, horizon, now):
        if (ge - gs) >= timedelta(minutes=HOS_RESTART_OFF_MIN):
            cycle_anchor = ge
    cycle_used = overlap_min(WORK_DUTIES, cycle_anchor)

    # --- driving minutes since the last qualifying 30-min break --------------
    break_anchor = window_start or horizon
    for gs, ge in _rest_gaps(intervals, break_anchor, now):
        if (ge - gs) >= timedelta(minutes=HOS_BREAK_MIN) and ge > break_anchor:
            break_anchor = ge
    since_break = overlap_min((DriverDuty.DRIVING,), break_anchor)

    violations = []
    if drive_used > HOS_DRIVE_LIMIT_MIN:
        violations.append("DRIVE_11H")
    if window_used > HOS_WINDOW_LIMIT_MIN:
        violations.append("WINDOW_14H")
    if cycle_used > HOS_CYCLE_LIMIT_MIN:
        violations.append("CYCLE_70H")
    if since_break > HOS_BREAK_AFTER_DRIVE_MIN:
        violations.append("BREAK_30M")

    return HosClocks(
        drive_min_used=drive_used,
        window_min_used=window_used,
        cycle_min_used=cycle_used,
        min_since_break=since_break,
        drive_min_remaining=max(0, HOS_DRIVE_LIMIT_MIN - drive_used),
        window_min_remaining=max(0, HOS_WINDOW_LIMIT_MIN - window_used),
        cycle_min_remaining=max(0, HOS_CYCLE_LIMIT_MIN - cycle_used),
        break_due_in_min=max(0, HOS_BREAK_AFTER_DRIVE_MIN - since_break),
        violations=violations,
    )
