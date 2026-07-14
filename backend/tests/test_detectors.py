"""Isolated watchdog tests on an in-memory DB (no dependency on the seeded
fleet.db), covering the false-positive regression: a driver's legally
mandated HOS rest must never be reported as a comms blackout."""
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    EtaState,
    ExceptionState,
    ExceptionType,
    FleetDriver,
    FleetException,
    FleetTruck,
    LiveLoad,
    LiveTrip,
    LoadStatus,
    TripStatus,
)
from app.sim import detectors

T0 = datetime(2026, 7, 14, 6, 0)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_trip(s: Session, **overrides) -> LiveTrip:
    s.add(FleetDriver(
        driver_id="D1", name="Test Driver", phone="+1", home_terminal="Dallas",
        years_experience=5, lat=32.7, lon=-96.8, on_time_rate=0.9, avg_mpg=6.5,
        incident_count=0, revenue_per_mile=2.0,
    ))
    s.add(FleetTruck(
        truck_id="TRK1", unit_number="1234", make="Volvo", model_year=2020,
        home_terminal="Dallas", status="Active", lat=32.7, lon=-96.8,
        odometer_miles=100000, last_pm_date=T0, next_pm_due=T0 + timedelta(days=90),
        annual_inspection_expiry=T0 + timedelta(days=200),
    ))
    s.add(LiveLoad(
        load_id="L1", source_load_id="SRC1", customer_id="C1", customer_name="Acme",
        route_id="R1", origin_city="Dallas", origin_state="TX", dest_city="Denver",
        dest_state="CO", pickup_facility_id="F1", dest_facility_id="F2",
        load_type="Dry Van", weight_lbs=30000, pieces=10, revenue=2000, fuel_surcharge=200,
        accessorial_charges=0, booking_type="Contract", distance_miles=800,
        pickup_window_start=T0, pickup_window_end=T0, delivery_deadline=T0 + timedelta(days=1),
        status=LoadStatus.IN_TRANSIT,
    ))
    trip = LiveTrip(
        trip_id="T1", load_id="L1", driver_id="D1", truck_id="TRK1",
        status=TripStatus.IN_TRANSIT, geometry_id=1, planned_eta=T0 + timedelta(hours=15),
        started_at=T0 - timedelta(hours=5), progress_miles=300, total_miles=800,
        speed_ewma_mph=58.0, eta_state=EtaState.NORMAL, last_ping_at=T0,
    )
    for k, v in overrides.items():
        setattr(trip, k, v)
    s.add(trip)
    s.commit()
    s.refresh(trip)
    return trip


def test_scheduled_hos_reset_is_not_flagged_dark(session):
    now = T0 + timedelta(minutes=600)  # 10h into a reset, gap far exceeds DARK_GAP_MIN
    trip = _make_trip(session, rest_until=now + timedelta(minutes=10), rest_kind="reset")
    load = session.get(LiveLoad, "L1")

    result = detectors._detect_dark(session, trip, load, now)

    assert result is None
    assert session.exec(select(FleetException)).all() == []


def test_scheduled_break_resolves_a_dark_exception_opened_just_before_it(session):
    now = T0 + timedelta(minutes=40)
    trip = _make_trip(session, last_ping_at=T0)
    load = session.get(LiveLoad, "L1")
    exc = FleetException(
        type=ExceptionType.DARK_LOAD, severity="HIGH", state=ExceptionState.OPEN,
        trip_id=trip.trip_id, title="dark", detected_at=T0 + timedelta(minutes=36),
        updated_at=T0 + timedelta(minutes=36),
    )
    session.add(exc)
    session.commit()

    trip.rest_until = now + timedelta(minutes=30)
    trip.rest_kind = "break"
    session.add(trip)
    session.commit()

    detectors._detect_dark(session, trip, load, now)

    assert exc.state == ExceptionState.RESOLVED


def test_genuine_gps_gap_without_a_tracked_rest_still_flags_dark(session):
    now = T0 + timedelta(minutes=50)
    trip = _make_trip(session, last_ping_at=T0)  # no rest_until: a real blackout
    load = session.get(LiveLoad, "L1")

    result = detectors._detect_dark(session, trip, load, now)

    assert result is not None
    assert result.type == ExceptionType.DARK_LOAD
    assert result.severity == "HIGH"


def test_dark_still_escalates_to_critical_past_double_the_gap(session):
    now = T0 + timedelta(minutes=90)
    trip = _make_trip(session, last_ping_at=T0)
    load = session.get(LiveLoad, "L1")

    result = detectors._detect_dark(session, trip, load, now)

    assert result is not None
    assert result.severity == "CRITICAL"
