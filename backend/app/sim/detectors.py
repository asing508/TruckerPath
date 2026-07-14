"""Watchdog: deterministic detection over the (possibly faulty) telemetry.

Each detector is a small state machine keyed on (type, subject) with
hysteresis so alerts don't flap. New/escalated exceptions are returned to the
engine, which hands HIGH/CRITICAL ones to the triage agent.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..config import (
    DARK_GAP_MIN,
    DETENTION_FREE_MIN,
    DETENTION_RATE_PER_HR,
    DEVIATION_CONFIRM_PINGS,
    DEVIATION_CORRIDOR_MI,
    ETA_CRITICAL_SLIP_MIN,
    ETA_RISK_SLIP_MIN,
    ETA_WATCH_SLIP_MIN,
    HOS_WARN_DRIVE_REMAINING_MIN,
)
from ..hos.ledger import compute_clocks
from ..hos.schedule import legal_elapsed_minutes
from ..models import (
    DriverDuty,
    EtaState,
    ExceptionState,
    ExceptionType,
    FleetDriver,
    FleetException,
    FleetTruck,
    HosEvent,
    LiveLoad,
    LiveTrip,
    TripStatus,
)
from ..streams import broadcaster
from .mover import polyline_for

ACTIVE_STATES = (
    ExceptionState.OPEN,
    ExceptionState.TRIAGING,
    ExceptionState.TRIAGED,
    ExceptionState.ACTIONED,
)


def _find_active(
    session: Session, type_: ExceptionType, *,
    trip_id: str | None = None, truck_id: str | None = None, driver_id: str | None = None,
) -> FleetException | None:
    q = select(FleetException).where(
        FleetException.type == type_,
        FleetException.state.in_(ACTIVE_STATES),  # type: ignore[attr-defined]
    )
    if trip_id:
        q = q.where(FleetException.trip_id == trip_id)
    if truck_id:
        q = q.where(FleetException.truck_id == truck_id)
    if driver_id:
        q = q.where(FleetException.driver_id == driver_id)
    return session.exec(q).first()


def _open(
    session: Session, now: datetime, type_: ExceptionType, severity: str, title: str,
    detail: dict, *, trip: LiveTrip | None = None,
    truck_id: str | None = None, driver_id: str | None = None,
) -> FleetException | None:
    """Upsert; returns the exception only when newly opened or escalated."""
    existing = _find_active(
        session, type_,
        trip_id=trip.trip_id if trip else None,
        truck_id=None if trip else truck_id,
        driver_id=None if (trip or truck_id) else driver_id,
    )
    if existing:
        escalated = (existing.severity != "CRITICAL" and severity == "CRITICAL")
        existing.severity = severity
        existing.detail = json.dumps(detail)
        existing.updated_at = now
        existing.title = title
        session.add(existing)
        return existing if escalated else None

    exc = FleetException(
        type=type_, severity=severity, title=title, detail=json.dumps(detail),
        trip_id=trip.trip_id if trip else None,
        driver_id=(trip.driver_id if trip else driver_id),
        truck_id=(trip.truck_id if trip else truck_id),
        load_id=trip.load_id if trip else None,
        detected_at=now, updated_at=now,
    )
    session.add(exc)
    session.flush()
    broadcaster.publish("feed", {
        "kind": "exception", "ts": now, "severity": severity,
        "text": title, "exception_id": exc.id, "trip_id": exc.trip_id,
    })
    return exc


def _resolve(session: Session, exc: FleetException, now: datetime, note: str) -> None:
    exc.state = ExceptionState.RESOLVED
    exc.updated_at = now
    detail = json.loads(exc.detail)
    detail["resolution"] = note
    exc.detail = json.dumps(detail)
    session.add(exc)
    broadcaster.publish("feed", {
        "kind": "resolved", "ts": now, "text": note, "exception_id": exc.id,
        "trip_id": exc.trip_id,
    })
    broadcaster.publish("exception", {"id": exc.id, "state": "RESOLVED"})


def tick(session: Session, now: datetime) -> list[FleetException]:
    new: list[FleetException] = []
    trips = session.exec(
        select(LiveTrip).where(LiveTrip.status.not_in([TripStatus.COMPLETED]))  # type: ignore[attr-defined]
    ).all()
    for trip in trips:
        load = session.get(LiveLoad, trip.load_id)
        driver = session.get(FleetDriver, trip.driver_id)
        if trip.status == TripStatus.IN_TRANSIT:
            new += filter(None, [
                _detect_dark(session, trip, load, now),
                _detect_deviation(session, trip, load, now),
                _detect_eta(session, trip, load, now),
            ])
        if trip.status in (TripStatus.AT_PICKUP, TripStatus.AT_DELIVERY):
            new += filter(None, [_detect_detention(session, trip, load, now)])
        new += filter(None, [_detect_hos(session, trip, driver, load, now)])

    for truck in session.exec(select(FleetTruck)).all():
        new += filter(None, [_detect_maintenance(session, truck, now)])
    return new


def _detect_dark(session, trip, load, now) -> FleetException | None:
    if not trip.last_ping_at:
        return None
    existing = _find_active(session, ExceptionType.DARK_LOAD, trip_id=trip.trip_id)
    # A known HOS break/reset silences pings by design - that's a legally
    # mandated stop, not a comms blackout, and must never be flagged as one.
    if trip.rest_until is not None and trip.rest_until > now:
        if existing:
            _resolve(session, existing, now,
                     f"{trip.trip_id} silent for a scheduled HOS "
                     f"{'reset' if trip.rest_kind == 'reset' else 'break'}, not a blackout")
        return None
    gap_min = (now - trip.last_ping_at).total_seconds() / 60.0
    if gap_min <= DARK_GAP_MIN:
        if existing and gap_min < 10:
            _resolve(session, existing, now,
                     f"GPS pings resumed on {trip.trip_id} after silence")
        return None
    severity = "CRITICAL" if gap_min > 2 * DARK_GAP_MIN else "HIGH"
    return _open(
        session, now, ExceptionType.DARK_LOAD, severity,
        f"Load {load.load_id} dark for {int(gap_min)} min en route to {load.dest_city}",
        {
            "gap_minutes": int(gap_min),
            "last_ping_at": trip.last_ping_at.isoformat(),
            "last_known_position": {"lat": trip and _last_pos(session, trip)[0],
                                     "lon": _last_pos(session, trip)[1]},
            "progress_miles": trip.progress_miles,
            "total_miles": trip.total_miles,
        },
        trip=trip,
    )


def _last_pos(session: Session, trip: LiveTrip) -> tuple[float, float]:
    truck = session.get(FleetTruck, trip.truck_id)
    return (truck.lat, truck.lon)


def _detect_deviation(session, trip, load, now) -> FleetException | None:
    if not trip.last_ping_at or trip.last_ping_at != now:
        return None  # evaluate only on fresh pings
    line = polyline_for(session, trip.geometry_id)
    truck = session.get(FleetTruck, trip.truck_id)
    dist = line.distance_from(truck.lat, truck.lon)
    if dist > DEVIATION_CORRIDOR_MI:
        trip.off_route_pings += 1
    else:
        trip.off_route_pings = 0
        if trip.off_route:
            trip.off_route = False
            existing = _find_active(session, ExceptionType.ROUTE_DEVIATION, trip_id=trip.trip_id)
            if existing:
                _resolve(session, existing, now,
                         f"{truck.unit_number} back on planned route")
        session.add(trip)
        return None
    session.add(trip)
    if trip.off_route_pings < DEVIATION_CONFIRM_PINGS or trip.off_route:
        return None
    trip.off_route = True
    return _open(
        session, now, ExceptionType.ROUTE_DEVIATION, "HIGH",
        f"{truck.unit_number} is {dist:.1f} mi off the planned corridor",
        {
            "distance_off_route_mi": round(dist, 2),
            "corridor_mi": DEVIATION_CORRIDOR_MI,
            "position": {"lat": truck.lat, "lon": truck.lon},
            "consecutive_pings": trip.off_route_pings,
        },
        trip=trip,
    )


_ETA_BANDS = [
    (EtaState.NORMAL, 0),
    (EtaState.WATCH, ETA_WATCH_SLIP_MIN),
    (EtaState.AT_RISK, ETA_RISK_SLIP_MIN),
    (EtaState.CRITICAL, ETA_CRITICAL_SLIP_MIN),
]


def _detect_eta(session, trip, load, now) -> FleetException | None:
    remaining = trip.total_miles - trip.progress_miles
    speed = max(trip.speed_ewma_mph or 45.0, 25.0)
    drive_min_needed = int(remaining / speed * 60)
    driver = session.get(FleetDriver, trip.driver_id)
    # projection includes the rest the driver is legally forced to take
    if trip.rest_until and trip.rest_until > now:
        rest_left = (trip.rest_until - now).total_seconds() / 60
        fresh = trip.rest_kind == "reset"
        elapsed = legal_elapsed_minutes(
            drive_min_needed,
            drive_used_min=0 if fresh else driver.drive_min_used,
            window_used_min=0 if fresh else driver.window_min_used,
            since_break_min=0,
        )
        projected = now + timedelta(minutes=rest_left + elapsed)
    else:
        projected = now + timedelta(minutes=legal_elapsed_minutes(
            drive_min_needed,
            drive_used_min=driver.drive_min_used,
            window_used_min=driver.window_min_used,
            since_break_min=driver.min_since_break,
        ))
    trip.projected_eta = projected
    slip_min = (projected - trip.planned_eta).total_seconds() / 60.0

    desired = EtaState.NORMAL
    for state, threshold in _ETA_BANDS:
        if slip_min >= threshold:
            desired = state
    order = [EtaState.NORMAL, EtaState.WATCH, EtaState.AT_RISK, EtaState.CRITICAL]
    cur_i, want_i = order.index(trip.eta_state), order.index(desired)
    if want_i > cur_i:
        trip.eta_state = desired
    elif want_i < cur_i:
        band_low = _ETA_BANDS[cur_i][1]
        if slip_min < band_low - 10:  # hysteresis on the way down
            trip.eta_state = desired
    session.add(trip)

    if trip.eta_state in (EtaState.AT_RISK, EtaState.CRITICAL):
        severity = "CRITICAL" if trip.eta_state == EtaState.CRITICAL else "HIGH"
        return _open(
            session, now, ExceptionType.ETA_RISK, severity,
            f"Load {load.load_id} projected {int(slip_min)} min late into {load.dest_city}",
            {
                "slip_minutes": int(slip_min),
                "planned_eta": trip.planned_eta.isoformat(),
                "projected_eta": projected.isoformat(),
                "speed_ewma_mph": trip.speed_ewma_mph,
                "remaining_miles": round(remaining, 1),
            },
            trip=trip,
        )
    existing = _find_active(session, ExceptionType.ETA_RISK, trip_id=trip.trip_id)
    if existing and trip.eta_state == EtaState.NORMAL:
        _resolve(session, existing, now, f"Load {load.load_id} back on schedule")
    return None


def _detect_detention(session, trip, load, now) -> FleetException | None:
    dwell_min = (now - trip.dwell_started_at).total_seconds() / 60.0
    billable = max(0.0, dwell_min - DETENTION_FREE_MIN)
    trip.detention_min = int(billable)
    session.add(trip)
    if dwell_min <= DETENTION_FREE_MIN:
        return None
    accrued = round(billable / 60.0 * DETENTION_RATE_PER_HR, 2)
    place = "shipper" if trip.status == TripStatus.AT_PICKUP else "consignee"
    return _open(
        session, now, ExceptionType.DETENTION, "HIGH",
        f"{load.load_id} detained at {place} {int(dwell_min)} min - ${accrued:,.0f} accruing",
        {
            "dwell_minutes": int(dwell_min),
            "free_minutes": DETENTION_FREE_MIN,
            "billable_minutes": int(billable),
            "accrued_usd": accrued,
            "facility_id": trip.dwell_facility_id,
            "since": trip.dwell_started_at.isoformat(),
        },
        trip=trip,
    )


def _detect_hos(session, trip, driver, load, now) -> FleetException | None:
    if driver.duty not in (DriverDuty.DRIVING, DriverDuty.ON_DUTY):
        return None
    worst = min(driver.drive_min_remaining_calc(), driver.window_min_remaining_calc())
    cycle_left = driver.cycle_min_remaining_calc()

    if worst >= HOS_WARN_DRIVE_REMAINING_MIN and cycle_left >= 240:
        existing = _find_active(session, ExceptionType.HOS_RISK, trip_id=trip.trip_id)
        if existing and worst > 90:
            _resolve(session, existing, now, f"{driver.name} HOS clocks recovered")
        return None
    if worst < HOS_WARN_DRIVE_REMAINING_MIN:
        severity = "CRITICAL" if worst < 20 else "HIGH"
        title = (f"{driver.name} hits a mandatory stop in {int(worst)} min - "
                 f"plan the rest stop or a relay")
    else:
        severity = "HIGH"
        title = (f"{driver.name} has {cycle_left / 60:.1f} h left in the 70h/8d "
                 f"cycle - tomorrow's assignments at risk")
    return _open(
        session, now, ExceptionType.HOS_RISK, severity, title,
        {
            "drive_min_remaining": driver.drive_min_remaining_calc(),
            "window_min_remaining": driver.window_min_remaining_calc(),
            "cycle_min_remaining": cycle_left,
            "violations": driver.hos_violation_flags or "none",
        },
        trip=trip,
    )


def _detect_maintenance(session, truck, now) -> FleetException | None:
    if truck.next_pm_due < now:
        overdue_days = (now - truck.next_pm_due).days
        return _open(
            session, now, ExceptionType.MAINTENANCE_DUE, "HIGH" if overdue_days > 2 else "WATCH",
            f"Unit {truck.unit_number} preventive maintenance overdue by {overdue_days} d",
            {"kind": "PM_OVERDUE", "next_pm_due": truck.next_pm_due.isoformat(),
             "overdue_days": overdue_days},
            truck_id=truck.truck_id,
        )
    days_to_expiry = (truck.annual_inspection_expiry - now).days
    if days_to_expiry <= 7:
        return _open(
            session, now, ExceptionType.MAINTENANCE_DUE, "HIGH",
            f"Unit {truck.unit_number} annual DOT inspection expires in {days_to_expiry} d",
            {"kind": "INSPECTION_EXPIRING",
             "expiry": truck.annual_inspection_expiry.isoformat(),
             "days_to_expiry": days_to_expiry},
            truck_id=truck.truck_id,
        )
    return None


def refresh_hos_snapshots(session: Session, now: datetime) -> None:
    events_by_driver: dict[str, list[HosEvent]] = {}
    for ev in session.exec(select(HosEvent)).all():
        events_by_driver.setdefault(ev.driver_id, []).append(ev)
    for driver in session.exec(select(FleetDriver)).all():
        clocks = compute_clocks(events_by_driver.get(driver.driver_id, []), now)
        driver.drive_min_used = clocks.drive_min_used
        driver.window_min_used = clocks.window_min_used
        driver.cycle_min_used = clocks.cycle_min_used
        driver.min_since_break = clocks.min_since_break
        driver.hos_violation_flags = ",".join(clocks.violations)
        session.add(driver)
