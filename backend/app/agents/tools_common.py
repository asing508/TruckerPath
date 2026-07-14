"""Read-only tools the agents use to investigate the fleet.

Every function returns plain JSON-able dicts sized for an LLM context;
they are the only way an agent sees the world.
"""
from __future__ import annotations

import heapq
import json
from datetime import datetime

from sqlmodel import Session, select

from ..config import DETENTION_RATE_PER_HR, LINEHAUL_BASE_MPH
from ..db import engine, raw_connection
from ..geo import haversine_miles
from ..models import (
    DriverDuty,
    FleetDriver,
    FleetException,
    FleetTruck,
    LiveLoad,
    LiveTrip,
    PingLog,
    SimState,
)
from .gemini import Tool, tool

ROAD_FACTOR = 1.18  # road miles over great-circle, US interstate average


def sim_now() -> datetime:
    with Session(engine) as s:
        return s.get(SimState, 1).sim_now


def _driver_dict(d: FleetDriver) -> dict:
    return {
        "driver_id": d.driver_id,
        "name": d.name,
        "home_terminal": d.home_terminal,
        "duty": d.duty,
        "on_trip": d.trip_id,
        "position": {"lat": round(d.lat, 4), "lon": round(d.lon, 4)},
        "hos": {
            "drive_min_remaining": d.drive_min_remaining_calc(),
            "window_min_remaining": d.window_min_remaining_calc(),
            "cycle_min_remaining": d.cycle_min_remaining_calc(),
            "min_since_break": d.min_since_break,
            "violations": d.hos_violation_flags or "none",
        },
        "history": {
            "on_time_rate": d.on_time_rate,
            "avg_mpg": d.avg_mpg,
            "incidents_career": d.incident_count,
            "revenue_per_mile": d.revenue_per_mile,
            "years_experience": d.years_experience,
        },
    }


@tool(
    "get_load",
    "Full detail of one load: customer, lane, revenue, windows, status.",
    {"type": "object", "properties": {"load_id": {"type": "string"}},
     "required": ["load_id"]},
)
def get_load(load_id: str) -> dict:
    with Session(engine) as s:
        load = s.get(LiveLoad, load_id)
        if not load:
            return {"error": f"load {load_id} not found"}
        return {
            "load_id": load.load_id,
            "customer": {"id": load.customer_id, "name": load.customer_name},
            "lane": f"{load.origin_city}, {load.origin_state} -> {load.dest_city}, {load.dest_state}",
            "route_id": load.route_id,
            "equipment": load.load_type,
            "weight_lbs": load.weight_lbs,
            "pieces": load.pieces,
            "revenue": load.revenue,
            "fuel_surcharge": load.fuel_surcharge,
            "accessorials": load.accessorial_charges,
            "booking_type": load.booking_type,
            "distance_miles": load.distance_miles,
            "pickup_window": [load.pickup_window_start.isoformat(),
                              load.pickup_window_end.isoformat()],
            "delivery_deadline": load.delivery_deadline.isoformat(),
            "status": load.status,
        }


@tool(
    "get_candidate_drivers",
    "Scored list of available fleet drivers for a load. Score blends deadhead "
    "miles to the pickup, HOS slack, lane familiarity, on-time history and "
    "safety record. Includes hard feasibility flags. Top 5 by score.",
    {"type": "object", "properties": {"load_id": {"type": "string"}},
     "required": ["load_id"]},
)
def get_candidate_drivers(load_id: str) -> dict:
    now = sim_now()
    with Session(engine) as s:
        load = s.get(LiveLoad, load_id)
        if not load:
            return {"error": f"load {load_id} not found"}
        conn = raw_connection()
        pickup = conn.execute(
            "SELECT lat, lon FROM city_coords WHERE city=? AND state=?",
            (load.origin_city, load.origin_state)).fetchone()
        idle = s.exec(select(FleetDriver).where(FleetDriver.trip_id == None)).all()  # noqa: E711
        scored = []
        for d in idle:
            deadhead = haversine_miles(d.lat, d.lon, pickup[0], pickup[1]) * ROAD_FACTOR
            hours_to_pickup = deadhead / 45.0 + 0.4
            eta_pickup = now.timestamp() + hours_to_pickup * 3600
            makes_window = eta_pickup <= load.pickup_window_end.timestamp()
            drive_needed_min = (deadhead + load.distance_miles) / LINEHAUL_BASE_MPH * 60
            hos_slack_min = min(d.drive_min_remaining_calc(), d.window_min_remaining_calc())
            needs_split = drive_needed_min > hos_slack_min
            familiarity = conn.execute(
                """SELECT COUNT(*) FROM trips t JOIN loads l ON l.load_id = t.load_id
                   WHERE t.driver_id = ? AND l.route_id = ?""",
                (d.driver_id, load.route_id)).fetchone()[0]
            score = (
                100.0
                - 0.06 * deadhead
                + 22.0 * d.on_time_rate
                + 1.5 * min(familiarity, 10)
                + 0.02 * hos_slack_min
                - 3.0 * d.incident_count
                - (25.0 if not makes_window else 0.0)
                - (18.0 if needs_split else 0.0)
            )
            flags = []
            if not makes_window:
                flags.append("cannot reach pickup inside window")
            if needs_split:
                flags.append("insufficient HOS to run leg nonstop - needs 10h reset en route")
            if d.cycle_min_remaining_calc() < 12 * 60:
                flags.append("under 12h left in 70h/8d cycle")
            scored.append((score, {
                **_driver_dict(d),
                "deadhead_miles": round(deadhead, 1),
                "eta_at_pickup": datetime.fromtimestamp(eta_pickup).isoformat(),
                "lane_trips_career": familiarity,
                "score": round(score, 1),
                "flags": flags,
            }))
        conn.close()
        top = heapq.nlargest(5, scored, key=lambda x: x[0])
        return {"pickup_city": load.origin_city,
                "candidates": [c for _, c in top],
                "idle_driver_count": len(idle)}


@tool(
    "get_driver",
    "Full profile + live HOS clocks for one driver.",
    {"type": "object", "properties": {"driver_id": {"type": "string"}},
     "required": ["driver_id"]},
)
def get_driver(driver_id: str) -> dict:
    with Session(engine) as s:
        d = s.get(FleetDriver, driver_id)
        return _driver_dict(d) if d else {"error": "not found"}


@tool(
    "get_lane_history",
    "3-year service history for a route: transit times, on-time rate, "
    "detention norms, revenue per mile.",
    {"type": "object", "properties": {"route_id": {"type": "string"}},
     "required": ["route_id"]},
)
def get_lane_history(route_id: str) -> dict:
    conn = raw_connection()
    row = conn.execute("SELECT * FROM lane_stats WHERE route_id=?", (route_id,)).fetchone()
    cols = [c[0] for c in conn.execute("SELECT * FROM lane_stats LIMIT 0").description]
    conn.close()
    return dict(zip(cols, row)) if row else {"error": "no history for route"}


@tool(
    "get_trip_state",
    "Live state of a trip: position, progress, speed, ETA vs plan, driver, truck.",
    {"type": "object", "properties": {"trip_id": {"type": "string"}},
     "required": ["trip_id"]},
)
def get_trip_state(trip_id: str) -> dict:
    with Session(engine) as s:
        t = s.get(LiveTrip, trip_id)
        if not t:
            return {"error": "trip not found"}
        load = s.get(LiveLoad, t.load_id)
        driver = s.get(FleetDriver, t.driver_id)
        truck = s.get(FleetTruck, t.truck_id)
        slip_min = None
        if t.projected_eta:
            slip_min = int((t.projected_eta - t.planned_eta).total_seconds() // 60)
        return {
            "trip_id": t.trip_id,
            "status": t.status,
            "load": get_load.fn(t.load_id),
            "driver": _driver_dict(driver),
            "truck": {"unit": truck.unit_number, "make": truck.make,
                      "fuel_pct": truck.fuel_pct, "position": {"lat": truck.lat, "lon": truck.lon}},
            "progress_miles": t.progress_miles,
            "total_miles": t.total_miles,
            "speed_ewma_mph": t.speed_ewma_mph,
            "planned_eta": t.planned_eta.isoformat(),
            "projected_eta": t.projected_eta.isoformat() if t.projected_eta else None,
            "eta_slip_minutes": slip_min,
            "eta_state": t.eta_state,
            "last_ping_at": t.last_ping_at.isoformat() if t.last_ping_at else None,
            "off_route": t.off_route,
            "detention_min_accrued": t.detention_min,
        }


@tool(
    "get_recent_pings",
    "Last GPS pings for a trip (most recent first).",
    {"type": "object", "properties": {"trip_id": {"type": "string"},
                                       "limit": {"type": "integer"}},
     "required": ["trip_id"]},
)
def get_recent_pings(trip_id: str, limit: int = 8) -> list[dict]:
    with Session(engine) as s:
        pings = s.exec(
            select(PingLog).where(PingLog.trip_id == trip_id)
            .order_by(PingLog.id.desc()).limit(min(limit, 20))  # type: ignore[arg-type]
        ).all()
        return [{"ts": p.ts.isoformat(), "lat": p.lat, "lon": p.lon,
                 "speed_mph": p.speed_mph} for p in pings]


@tool(
    "find_nearby_drivers",
    "Idle fleet drivers within a radius of a point, nearest first, with HOS.",
    {"type": "object", "properties": {
        "lat": {"type": "number"}, "lon": {"type": "number"},
        "radius_miles": {"type": "number"}},
     "required": ["lat", "lon"]},
)
def find_nearby_drivers(lat: float, lon: float, radius_miles: float = 300.0) -> list[dict]:
    with Session(engine) as s:
        idle = s.exec(select(FleetDriver).where(FleetDriver.trip_id == None)).all()  # noqa: E711
        out = []
        for d in idle:
            dist = haversine_miles(lat, lon, d.lat, d.lon) * ROAD_FACTOR
            if dist <= radius_miles:
                out.append({**_driver_dict(d), "distance_miles": round(dist, 1)})
        return sorted(out, key=lambda x: x["distance_miles"])[:6]


@tool(
    "get_exception",
    "Detector evidence for one exception.",
    {"type": "object", "properties": {"exception_id": {"type": "integer"}},
     "required": ["exception_id"]},
)
def get_exception(exception_id: int) -> dict:
    with Session(engine) as s:
        e = s.get(FleetException, exception_id)
        if not e:
            return {"error": "not found"}
        return {
            "id": e.id, "type": e.type, "severity": e.severity, "state": e.state,
            "title": e.title, "evidence": json.loads(e.detail),
            "trip_id": e.trip_id, "driver_id": e.driver_id,
            "truck_id": e.truck_id, "load_id": e.load_id,
            "detected_at": e.detected_at.isoformat(),
        }


@tool(
    "get_customer_profile",
    "Customer account: credit terms, revenue potential, and our historical "
    "on-time performance on their freight.",
    {"type": "object", "properties": {"customer_id": {"type": "string"}},
     "required": ["customer_id"]},
)
def get_customer_profile(customer_id: str) -> dict:
    conn = raw_connection()
    row = conn.execute(
        """SELECT customer_name, customer_type, credit_terms_days, annual_revenue_potential
           FROM customers WHERE customer_id=?""", (customer_id,)).fetchone()
    if not row:
        conn.close()
        return {"error": "customer not found"}
    otd = conn.execute(
        """SELECT AVG(e.on_time_flag), COUNT(*)
           FROM delivery_events e
           JOIN loads l ON l.load_id = e.load_id
           WHERE l.customer_id=? AND e.event_type='Delivery'""", (customer_id,)).fetchone()
    conn.close()
    return {
        "customer_id": customer_id, "name": row[0], "type": row[1],
        "credit_terms_days": row[2], "annual_revenue_potential": row[3],
        "our_on_time_rate_for_them": round(otd[0] or 0, 3),
        "historical_deliveries": otd[1],
    }


@tool(
    "get_detention_math",
    "Detention economics for a trip currently dwelling: accrual so far and "
    "hourly burn rate.",
    {"type": "object", "properties": {"trip_id": {"type": "string"}},
     "required": ["trip_id"]},
)
def get_detention_math(trip_id: str) -> dict:
    with Session(engine) as s:
        t = s.get(LiveTrip, trip_id)
        if not t or not t.dwell_started_at:
            return {"error": "trip is not dwelling"}
        now = sim_now()
        dwell = (now - t.dwell_started_at).total_seconds() / 60
        return {
            "dwell_minutes": int(dwell),
            "free_time_minutes": 120,
            "billable_minutes": max(0, int(dwell - 120)),
            "rate_per_hour": DETENTION_RATE_PER_HR,
            "accrued_usd": round(max(0.0, dwell - 120) / 60 * DETENTION_RATE_PER_HR, 2),
        }


COMMON_TOOLS: list[Tool] = [
    get_load, get_candidate_drivers, get_driver, get_lane_history,
    get_trip_state, get_recent_pings, find_nearby_drivers, get_exception,
    get_customer_profile, get_detention_math,
]
