from datetime import datetime

from app.hos.ledger import compute_clocks
from app.hos.schedule import (
    legal_blocks,
    legal_elapsed_minutes,
    schedule_events,
)
from app.models import DriverDuty, HosEvent


def test_short_leg_has_no_breaks():
    blocks = legal_blocks(6 * 60)
    assert [b.duty for b in blocks] == [DriverDuty.DRIVING]
    assert legal_elapsed_minutes(6 * 60) == 360


def test_break_inserted_after_eight_hours():
    blocks = legal_blocks(10 * 60)
    duties = [b.duty for b in blocks]
    assert duties == [DriverDuty.DRIVING, DriverDuty.OFF, DriverDuty.DRIVING]
    assert blocks[0].minutes == 8 * 60
    assert blocks[1].minutes == 35


def test_reset_inserted_after_drive_limit():
    # 19h of wheel time cannot fit in one duty window
    blocks = legal_blocks(19 * 60)
    off = [b.minutes for b in blocks if b.duty == DriverDuty.OFF]
    assert 600 in off  # a 10h reset
    # elapsed = 19h drive + one 35m break in day one, reset, then day two
    assert legal_elapsed_minutes(19 * 60) >= 19 * 60 + 600


def test_generated_history_is_violation_free():
    """The seeder's whole point: mid-trip drivers must be legal at t0."""
    now = datetime(2026, 7, 14, 6, 0)
    for drive_min in (90, 5 * 60, 9 * 60, 14 * 60, 22 * 60, 30 * 60):
        events = [
            HosEvent(driver_id="D", duty=d, start=s, end=e)
            for d, s, e in schedule_events(drive_min, now)
        ]
        clocks = compute_clocks(events, now)
        assert clocks.violations == [], (drive_min, clocks)
        assert clocks.drive_min_remaining >= 0


def test_resuming_from_used_clocks():
    # 3h more wheel time with the 11h drive clock fully spent: reset first
    blocks = legal_blocks(3 * 60, drive_used_min=11 * 60,
                          window_used_min=12 * 60, since_break_min=200)
    assert blocks[0].duty == DriverDuty.OFF
    assert blocks[0].minutes == 600
