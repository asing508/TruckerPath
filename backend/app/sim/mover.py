"""Advances the physical world one tick: truck motion, pings, duty flips.

Faults from the seed scripts distort *telemetry and speed* here; nothing in
this module raises alerts. Detection lives in detectors.py and has to earn it.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..config import (
    LINEHAUL_BASE_MPH,
    PING_INTERVAL_SIM_MIN,
    PING_LOG_CAP_PER_TRIP,
    SPEED_EWMA_ALPHA,
    HOS_BREAK_AFTER_DRIVE_MIN,
    HOS_BREAK_MIN,
)
from ..geo import Polyline
from ..models import (
    DriverDuty,
    FleetDriver,
    FleetTruck,
    HosEvent,
    LiveLoad,
    LiveTrip,
    LoadStatus,
    PingLog,
    RouteGeometry,
    TripStatus,
)
from ..streams import broadcaster

DELIVERY_DWELL_MIN = 40
DEFAULT_PICKUP_SERVICE_MIN = 45
AVG_MPG = 6.8
TANK_GALLONS = 200.0

_polyline_cache: dict[int, Polyline] = {}


def polyline_for(session: Session, geometry_id: int) -> Polyline:
    if geometry_id not in _polyline_cache:
        geom = session.get(RouteGeometry, geometry_id)
        _polyline_cache[geometry_id] = Polyline.from_points(json.loads(geom.encoded_polyline))
    return _polyline_cache[geometry_id]


def set_duty(session: Session, driver: FleetDriver, duty: DriverDuty, now: datetime) -> None:
    if driver.duty == duty:
        return
    open_ev = session.exec(
        select(HosEvent).where(HosEvent.driver_id == driver.driver_id, HosEvent.end == None)  # noqa: E711
    ).first()
    if open_ev:
        open_ev.end = now
        session.add(open_ev)
    session.add(HosEvent(driver_id=driver.driver_id, duty=duty, start=now))
    driver.duty = duty
    session.add(driver)


def _speed_noise(trip_id: str, sim_now: datetime) -> float:
    band = int(sim_now.timestamp() // 420)  # stable within 7-minute bands
    return random.Random(hash((trip_id, band))).uniform(0.92, 1.06)


def _fault(trip: LiveTrip) -> dict:
    return json.loads(trip.fault_script or "{}")


def _save_fault(trip: LiveTrip, fault: dict) -> None:
    trip.fault_script = json.dumps(fault)


def _lateral_offset(lat: float, lon: float, heading: float, offset_mi: float) -> tuple[float, float]:
    perp = math.radians((heading + 90.0) % 360.0)
    dlat = offset_mi * math.cos(perp) / 69.046
    dlon = offset_mi * math.sin(perp) / (69.046 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def tick(session: Session, sim_now: datetime, dt: timedelta) -> None:
    dt_hours = dt.total_seconds() / 3600.0
    trips = session.exec(
        select(LiveTrip).where(LiveTrip.status.not_in([TripStatus.COMPLETED]))  # type: ignore[attr-defined]
    ).all()
    for trip in trips:
        driver = session.get(FleetDriver, trip.driver_id)
        truck = session.get(FleetTruck, trip.truck_id)
        if trip.status == TripStatus.IN_TRANSIT:
            _tick_linehaul(session, trip, driver, truck, sim_now, dt_hours)
        elif trip.status in (TripStatus.AT_PICKUP, TripStatus.AT_DELIVERY):
            _tick_dwell(session, trip, driver, truck, sim_now)
        elif trip.status == TripStatus.EN_ROUTE_PICKUP:
            _tick_deadhead(session, trip, driver, truck, sim_now)
        session.add_all([trip, driver, truck])


def _tick_linehaul(
    session: Session,
    trip: LiveTrip,
    driver: FleetDriver,
    truck: FleetTruck,
    sim_now: datetime,
    dt_hours: float,
) -> None:
    # HOS behavior: the ELD would force these stops, so the sim takes them
    if trip.rest_until:
        if sim_now >= trip.rest_until:
            kind = trip.rest_kind
            trip.rest_until = None
            trip.rest_kind = ""
            set_duty(session, driver, DriverDuty.DRIVING, sim_now)
            broadcaster.publish("feed", {
                "kind": "break_end", "ts": sim_now,
                "text": (f"{driver.name} back on the road after "
                         f"{'10-h reset' if kind == 'reset' else '30-min break'}"),
                "trip_id": trip.trip_id,
            })
        else:
            truck.speed_mph = 0.0
            return
    else:
        worst = min(driver.drive_min_remaining_calc(), driver.window_min_remaining_calc())
        if worst <= 8:
            trip.rest_until = sim_now + timedelta(minutes=10 * 60 + 10)
            trip.rest_kind = "reset"
            set_duty(session, driver, DriverDuty.OFF, sim_now)
            truck.speed_mph = 0.0
            broadcaster.publish("feed", {
                "kind": "break_start", "ts": sim_now,
                "text": f"{driver.name} out of hours - parked for mandatory 10-h reset",
                "trip_id": trip.trip_id,
            })
            return
        if driver.min_since_break >= HOS_BREAK_AFTER_DRIVE_MIN - 12:
            trip.rest_until = sim_now + timedelta(minutes=HOS_BREAK_MIN + 5)
            trip.rest_kind = "break"
            set_duty(session, driver, DriverDuty.OFF, sim_now)
            truck.speed_mph = 0.0
            broadcaster.publish("feed", {
                "kind": "break_start", "ts": sim_now,
                "text": f"{driver.name} pulled in for the required 30-min break",
                "trip_id": trip.trip_id,
            })
            return

    fault = _fault(trip)
    frac = trip.progress_miles / max(trip.total_miles, 0.1)

    factor = 1.0
    if fault.get("type") == "slowdown" and fault["from"] <= frac <= fault["to"]:
        factor = fault["factor"]

    speed = LINEHAUL_BASE_MPH * factor * _speed_noise(trip.trip_id, sim_now)
    moved = speed * dt_hours
    trip.progress_miles = min(trip.total_miles, trip.progress_miles + moved)
    truck.odometer_miles += moved
    truck.fuel_pct = max(4.0, truck.fuel_pct - moved / (AVG_MPG * TANK_GALLONS) * 100.0)

    # arrival
    if trip.progress_miles >= trip.total_miles - 0.05:
        trip.status = TripStatus.AT_DELIVERY
        load = session.get(LiveLoad, trip.load_id)
        trip.dwell_facility_id = load.dest_facility_id
        trip.dwell_started_at = sim_now
        truck.speed_mph = 0.0
        set_duty(session, driver, DriverDuty.ON_DUTY, sim_now)
        broadcaster.publish("feed", {
            "kind": "arrival", "ts": sim_now,
            "text": f"{truck.unit_number} arrived at {load.dest_city}, {load.dest_state} consignee",
            "trip_id": trip.trip_id,
        })
        return

    # dark-window bookkeeping
    dark_active = False
    if fault.get("type") == "dark":
        if frac >= fault["at_progress"] and "started_at" not in fault:
            fault["started_at"] = sim_now.isoformat()
            _save_fault(trip, fault)
        if "started_at" in fault:
            started = datetime.fromisoformat(fault["started_at"])
            dark_active = sim_now < started + timedelta(minutes=fault["duration_min"])

    if dark_active:
        return  # GPS silent: no ping, map position freezes at last report

    if trip.last_ping_at and (sim_now - trip.last_ping_at) < timedelta(minutes=PING_INTERVAL_SIM_MIN):
        return

    line = polyline_for(session, trip.geometry_id)
    lat, lon, heading = line.point_at(trip.progress_miles)
    if fault.get("type") == "offset" and fault["from"] <= frac <= fault["to"]:
        ramp = math.sin(math.pi * (frac - fault["from"]) / (fault["to"] - fault["from"]))
        lat, lon = _lateral_offset(lat, lon, heading, fault["offset_mi"] * ramp)

    trip.last_ping_at = sim_now
    trip.speed_ewma_mph = round(
        SPEED_EWMA_ALPHA * speed + (1 - SPEED_EWMA_ALPHA) * (trip.speed_ewma_mph or speed), 1)
    truck.lat, truck.lon, truck.heading_deg, truck.speed_mph = lat, lon, heading, round(speed, 1)
    driver.lat, driver.lon = lat, lon
    session.add(PingLog(trip_id=trip.trip_id, ts=sim_now, lat=lat, lon=lon,
                        speed_mph=round(speed, 1), heading_deg=round(heading, 1)))
    _prune_pings(session, trip.trip_id)


def _prune_pings(session: Session, trip_id: str) -> None:
    ids = session.exec(
        select(PingLog.id).where(PingLog.trip_id == trip_id).order_by(PingLog.id.desc())  # type: ignore[arg-type]
    ).all()
    for stale_id in ids[PING_LOG_CAP_PER_TRIP:]:
        session.delete(session.get(PingLog, stale_id))


def _tick_deadhead(
    session: Session,
    trip: LiveTrip,
    driver: FleetDriver,
    truck: FleetTruck,
    sim_now: datetime,
) -> None:
    """Bobtail leg to the pickup dock: linear glide between stored endpoints."""
    fault = _fault(trip)
    leg = fault.get("assign")
    if not leg or not trip.pickup_arrival_at:
        trip.status = TripStatus.AT_PICKUP
        trip.dwell_started_at = sim_now
        return
    depart = datetime.fromisoformat(leg["depart"])
    total = (trip.pickup_arrival_at - depart).total_seconds()
    f = 1.0 if total <= 0 else min(1.0, (sim_now - depart).total_seconds() / total)
    (flat, flon), (tlat, tlon) = leg["from"], leg["to"]
    truck.lat = flat + (tlat - flat) * f
    truck.lon = flon + (tlon - flon) * f
    truck.speed_mph = 42.0 if f < 1.0 else 0.0
    driver.lat, driver.lon = truck.lat, truck.lon
    trip.last_ping_at = sim_now
    if sim_now >= trip.pickup_arrival_at:
        load = session.get(LiveLoad, trip.load_id)
        trip.status = TripStatus.AT_PICKUP
        trip.dwell_facility_id = load.pickup_facility_id
        trip.dwell_started_at = sim_now
        set_duty(session, driver, DriverDuty.ON_DUTY, sim_now)
        broadcaster.publish("feed", {
            "kind": "at_pickup", "ts": sim_now,
            "text": f"{truck.unit_number} checked in at {load.origin_city} shipper",
            "trip_id": trip.trip_id,
        })


def _tick_dwell(
    session: Session,
    trip: LiveTrip,
    driver: FleetDriver,
    truck: FleetTruck,
    sim_now: datetime,
) -> None:
    dwell_min = (sim_now - trip.dwell_started_at).total_seconds() / 60.0
    fault = _fault(trip)

    if trip.status == TripStatus.AT_PICKUP:
        service_min = fault.get("extra_min", DEFAULT_PICKUP_SERVICE_MIN)
        if dwell_min >= service_min:
            trip.status = TripStatus.IN_TRANSIT
            trip.dwell_facility_id = None
            trip.dwell_started_at = None
            load = session.get(LiveLoad, trip.load_id)
            load.status = LoadStatus.IN_TRANSIT
            session.add(load)
            set_duty(session, driver, DriverDuty.DRIVING, sim_now)
            broadcaster.publish("feed", {
                "kind": "departure", "ts": sim_now,
                "text": f"{truck.unit_number} loaded and rolling out of {load.origin_city}",
                "trip_id": trip.trip_id,
            })
    else:  # AT_DELIVERY
        if dwell_min >= DELIVERY_DWELL_MIN:
            trip.status = TripStatus.COMPLETED
            trip.completed_at = sim_now
            load = session.get(LiveLoad, trip.load_id)
            load.status = LoadStatus.DELIVERED
            session.add(load)
            driver.trip_id = None
            truck.trip_id = None
            truck.speed_mph = 0.0
            set_duty(session, driver, DriverDuty.OFF, sim_now)
            broadcaster.publish("feed", {
                "kind": "delivered", "ts": sim_now,
                "text": f"Load {load.load_id} delivered at {load.dest_city}, {load.dest_state}",
                "trip_id": trip.trip_id, "load_id": load.load_id,
            })
