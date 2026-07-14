"""FMCSA-legal drive-schedule arithmetic.

One walker converts "hours of wheel time" into an elapsed timeline with the
mandatory 30-minute breaks and 10-hour resets inserted. The seeder uses it to
generate honest duty histories for trips already underway; trip planning and
the ETA detector use it so promised and projected arrival times account for
rest the driver is legally forced to take.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import (
    HOS_BREAK_AFTER_DRIVE_MIN,
    HOS_BREAK_MIN,
    HOS_DRIVE_LIMIT_MIN,
    HOS_WINDOW_LIMIT_MIN,
)
from ..models import DriverDuty

RESET_MIN = 10 * 60
BREAK_TAKEN_MIN = HOS_BREAK_MIN + 5  # drivers don't cut the break to the second
PRE_TRIP_MIN = 25


@dataclass
class Block:
    duty: DriverDuty
    minutes: int


def legal_blocks(
    drive_min_needed: int,
    *,
    drive_used_min: int = 0,
    window_used_min: int = 0,
    since_break_min: int = 0,
) -> list[Block]:
    """Duty blocks to complete the given wheel time, starting from the given
    clock state, obeying 11h drive / 14h window / 30-min break rules."""
    blocks: list[Block] = []
    drive_left = drive_min_needed
    drive_used = drive_used_min
    window_used = window_used_min
    since_break = since_break_min

    while drive_left > 0:
        chunk = min(
            drive_left,
            HOS_DRIVE_LIMIT_MIN - drive_used,
            HOS_WINDOW_LIMIT_MIN - window_used,
            HOS_BREAK_AFTER_DRIVE_MIN - since_break,
        )
        if chunk <= 0:
            need_reset = (
                drive_used >= HOS_DRIVE_LIMIT_MIN - 5
                or window_used >= HOS_WINDOW_LIMIT_MIN - 5
            )
            if need_reset:
                blocks.append(Block(DriverDuty.OFF, RESET_MIN))
                drive_used = window_used = since_break = 0
            else:
                blocks.append(Block(DriverDuty.OFF, BREAK_TAKEN_MIN))
                window_used += BREAK_TAKEN_MIN
                since_break = 0
            continue
        blocks.append(Block(DriverDuty.DRIVING, chunk))
        drive_left -= chunk
        drive_used += chunk
        window_used += chunk
        since_break += chunk
    return blocks


def legal_elapsed_minutes(drive_min_needed: int, **clock_state: int) -> int:
    return sum(b.minutes for b in legal_blocks(drive_min_needed, **clock_state))


def schedule_events(
    drive_min_done: int, ends_at: datetime
) -> list[tuple[DriverDuty, datetime, datetime | None]]:
    """Duty intervals for a leg with `drive_min_done` wheel minutes that is
    still in progress at `ends_at`. The trailing interval is left open.
    Returns [(duty, start, end)], starting with a short ON_DUTY pre-trip."""
    blocks = legal_blocks(drive_min_done)
    total = sum(b.minutes for b in blocks) + PRE_TRIP_MIN
    start = ends_at - timedelta(minutes=total)
    events: list[tuple[DriverDuty, datetime, datetime | None]] = [
        (DriverDuty.ON_DUTY, start, start + timedelta(minutes=PRE_TRIP_MIN))
    ]
    cursor = start + timedelta(minutes=PRE_TRIP_MIN)
    for i, b in enumerate(blocks):
        end = cursor + timedelta(minutes=b.minutes)
        is_last = i == len(blocks) - 1
        events.append((b.duty, cursor, None if is_last else end))
        cursor = end
    return events


def trip_start_for_progress(drive_min_done: int, now: datetime) -> datetime:
    """When the trip must have started for the wheels to have turned this long."""
    elapsed = legal_elapsed_minutes(drive_min_done) + PRE_TRIP_MIN
    return now - timedelta(minutes=elapsed)
