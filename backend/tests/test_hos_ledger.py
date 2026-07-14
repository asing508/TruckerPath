from datetime import datetime, timedelta

from app.hos.ledger import compute_clocks
from app.models import DriverDuty, HosEvent

T0 = datetime(2026, 7, 13, 6, 0)


def ev(duty, start_h, end_h=None):
    return HosEvent(
        driver_id="D1",
        duty=duty,
        start=T0 + timedelta(hours=start_h),
        end=None if end_h is None else T0 + timedelta(hours=end_h),
    )


def test_fresh_driver_has_full_clocks():
    clocks = compute_clocks([], T0)
    assert clocks.drive_min_remaining == 11 * 60
    assert clocks.window_min_remaining == 14 * 60
    assert clocks.cycle_min_remaining == 70 * 60
    assert clocks.violations == []


def test_window_starts_at_first_work_after_10h_rest():
    events = [
        ev(DriverDuty.ON_DUTY, 0, 0.5),
        ev(DriverDuty.DRIVING, 0.5, 4.5),
    ]
    now = T0 + timedelta(hours=4.5)
    clocks = compute_clocks(events, now)
    assert clocks.drive_min_used == 240
    assert clocks.window_min_used == 270  # window anchored at hour 0
    assert clocks.min_since_break == 240


def test_thirty_min_break_resets_break_clock_not_drive_clock():
    events = [
        ev(DriverDuty.DRIVING, 0, 5),
        ev(DriverDuty.OFF, 5, 5.6),      # 36-minute break
        ev(DriverDuty.DRIVING, 5.6, 8),
    ]
    now = T0 + timedelta(hours=8)
    clocks = compute_clocks(events, now)
    assert clocks.drive_min_used == 444   # 5h + 2.4h
    assert clocks.min_since_break == 144  # only the post-break driving


def test_drive_limit_violation_flagged():
    events = [ev(DriverDuty.DRIVING, 0, 11.5)]
    clocks = compute_clocks(events, T0 + timedelta(hours=11.5))
    assert "DRIVE_11H" in clocks.violations
    assert clocks.drive_min_remaining == 0


def test_ten_hour_rest_resets_daily_window():
    events = [
        ev(DriverDuty.DRIVING, 0, 10),           # long day yesterday
        ev(DriverDuty.OFF, 10, 21),              # 11h off = qualifying rest
        ev(DriverDuty.DRIVING, 21, 23),          # fresh window
    ]
    now = T0 + timedelta(hours=23)
    clocks = compute_clocks(events, now)
    assert clocks.drive_min_used == 120
    assert clocks.window_min_used == 120
    # but the cycle still remembers both days
    assert clocks.cycle_min_used == 12 * 60


def test_cycle_sums_eight_days_and_restart_clears_it():
    events = []
    for day in range(6):
        events.append(ev(DriverDuty.DRIVING, day * 24, day * 24 + 10))
    now = T0 + timedelta(days=5, hours=12)
    clocks = compute_clocks(events, now)
    assert clocks.cycle_min_used == 60 * 60  # 6 days x 10h

    # a 34h restart wipes the recap
    events.append(ev(DriverDuty.OFF, 5 * 24 + 10, 5 * 24 + 10 + 35))
    events.append(ev(DriverDuty.DRIVING, 5 * 24 + 45, 5 * 24 + 47))
    now2 = T0 + timedelta(hours=5 * 24 + 47)
    clocks2 = compute_clocks(events, now2)
    assert clocks2.cycle_min_used == 120


def test_open_event_clips_at_now():
    events = [ev(DriverDuty.DRIVING, 0, None)]
    clocks = compute_clocks(events, T0 + timedelta(hours=3))
    assert clocks.drive_min_used == 180
