"""Builds the live-ops world the simulator runs forward from T0.

Everything is carved from the warehouse: the fleet is the Dallas/Houston/OKC
terminal cluster, live loads are real historical load rows re-anchored to the
sim clock, and route geometry is real road shape (OSRM, cached). Telemetry
faults for the demo are *injected into the world* (scripts on trips, seeded HOS
history); the watchdog has to detect them honestly.
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..config import (
    FLEET_TERMINALS,
    LINEHAUL_BASE_MPH,
    PM_INTERVAL_DAYS,
    ANNUAL_INSPECTION_DAYS,
    SEED,
    SIM_SPEED_DEFAULT,
)
from ..db import engine
from ..geo import Polyline
from ..hos.ledger import compute_clocks
from ..hos.schedule import legal_elapsed_minutes, schedule_events
from ..models import (
    DocPacket,
    DriverDuty,
    EtaState,
    FleetDriver,
    FleetTruck,
    HosEvent,
    LiveLoad,
    LiveTrip,
    LoadStatus,
    RouteGeometry,
    SimState,
    TripStatus,
)
from .osrm import fetch_road_polyline

DOCK_BUFFER_HOURS = 1.0
PLANNING_MPH = 52.0  # conservative speed used for customer-quoted ETAs


def _city_coords(cur: sqlite3.Cursor) -> dict[tuple[str, str], tuple[float, float]]:
    return {(c, s): (lat, lon) for c, s, lat, lon in
            cur.execute("SELECT city, state, lat, lon FROM city_coords")}


def _facility_for_city(cur: sqlite3.Cursor) -> dict[tuple[str, str], tuple[str, float, float]]:
    out: dict[tuple[str, str], tuple[str, float, float]] = {}
    for fid, city, state, lat, lon in cur.execute(
        "SELECT facility_id, city, state, latitude, longitude FROM facilities ORDER BY facility_id"
    ):
        out.setdefault((city, state), (fid, lat, lon))
    return out


class WorldBuilder:
    def __init__(self, conn: sqlite3.Connection, session: Session, t0: datetime):
        self.cur = conn.cursor()
        self.session = session
        self.t0 = t0
        self.rng = random.Random(SEED)
        self.coords = _city_coords(self.cur)
        self.facility = _facility_for_city(self.cur)
        self.geometry_ids: dict[str, int] = {}
        self._load_seq = 0
        self._trip_seq = 0

    # ---- geometry ------------------------------------------------------------
    def geometry(self, o: tuple[str, str], d: tuple[str, str]) -> RouteGeometry:
        key = f"{o[0]},{o[1]}->{d[0]},{d[1]}"
        if key in self.geometry_ids:
            return self.session.get(RouteGeometry, self.geometry_ids[key])
        cached = self.session.exec(
            select(RouteGeometry).where(RouteGeometry.lane_key == key)
        ).first()
        if cached:
            self.geometry_ids[key] = cached.id
            return cached
        (olat, olon), (dlat, dlon) = self.coords[o], self.coords[d]
        pts, miles, hours, source = fetch_road_polyline(olat, olon, dlat, dlon)
        geom = RouteGeometry(
            lane_key=key,
            encoded_polyline=json.dumps(pts),
            distance_miles=round(miles, 1),
            duration_hours=round(hours, 2),
            source=source,
        )
        self.session.add(geom)
        self.session.flush()
        self.geometry_ids[key] = geom.id
        return geom

    # ---- entities ------------------------------------------------------------
    def carve_fleet(self) -> tuple[list[FleetTruck], list[FleetDriver]]:
        placeholders = ",".join("?" for _ in FLEET_TERMINALS)
        trucks = []
        rows = self.cur.execute(
            f"""SELECT truck_id, unit_number, make, model_year, home_terminal, status,
                       acquisition_mileage
                FROM trucks
                WHERE home_terminal IN ({placeholders}) AND status != 'Inactive'
                ORDER BY truck_id""",
            FLEET_TERMINALS,
        ).fetchall()
        for truck_id, unit, make, myear, terminal, status, acq_miles in rows:
            lat, lon = self.coords[(terminal, self._state_of(terminal))]
            last_pm = self.cur.execute(
                """SELECT MAX(maintenance_date) FROM maintenance_records
                   WHERE truck_id = ? AND maintenance_type IN ('Preventive','Inspection')""",
                (truck_id,),
            ).fetchone()[0]
            # Re-anchor the truck's real PM cadence into the sim window.
            pm_age_days = self.rng.randint(12, 70)
            last_pm_date = self.t0 - timedelta(days=pm_age_days)
            trucks.append(FleetTruck(
                truck_id=truck_id,
                unit_number=unit,
                make=make,
                model_year=myear,
                home_terminal=terminal,
                status=status,
                lat=lat + self.rng.uniform(-0.01, 0.01),
                lon=lon + self.rng.uniform(-0.01, 0.01),
                odometer_miles=acq_miles + self.rng.randint(180_000, 420_000),
                last_pm_date=last_pm_date,
                next_pm_due=last_pm_date + timedelta(days=PM_INTERVAL_DAYS),
                annual_inspection_expiry=self.t0 + timedelta(days=self.rng.randint(40, 300)),
            ))

        drivers = []
        rows = self.cur.execute(
            f"""SELECT s.driver_id, s.name, s.home_terminal, s.years_experience,
                       s.on_time_rate, s.avg_mpg, s.incident_count, s.revenue_per_mile
                FROM driver_stats s
                WHERE s.home_terminal IN ({placeholders}) AND s.employment_status = 'Active'
                ORDER BY s.driver_id""",
            FLEET_TERMINALS,
        ).fetchall()
        for i, (did, name, terminal, yexp, otr, mpg, inc, rpm) in enumerate(rows):
            lat, lon = self.coords[(terminal, self._state_of(terminal))]
            drivers.append(FleetDriver(
                driver_id=did,
                name=name,
                phone=f"+1 (214) 555-0{100 + i}",
                home_terminal=terminal,
                years_experience=yexp,
                lat=lat + self.rng.uniform(-0.01, 0.01),
                lon=lon + self.rng.uniform(-0.01, 0.01),
                on_time_rate=round(otr, 3),
                avg_mpg=round(mpg or 6.5, 2),
                incident_count=inc,
                revenue_per_mile=round(rpm, 3),
            ))
        return trucks, drivers

    def _state_of(self, city: str) -> str:
        for (c, s) in self.coords:
            if c == city:
                return s
        raise KeyError(city)

    # ---- loads ---------------------------------------------------------------
    def _fleet_routes(self) -> list[tuple]:
        placeholders = ",".join("?" for _ in FLEET_TERMINALS)
        return self.cur.execute(
            f"""SELECT route_id, origin_city, origin_state, destination_city, destination_state,
                       typical_distance_miles
                FROM routes
                WHERE origin_city IN ({placeholders}) OR destination_city IN ({placeholders})
                ORDER BY route_id""",
            FLEET_TERMINALS + FLEET_TERMINALS,
        ).fetchall()

    def make_load(self, route_row: tuple, pickup_start: datetime, status: LoadStatus) -> LiveLoad:
        """Re-anchor a real historical load from this route into the sim window."""
        route_id, oc, os_, dc, ds, dist = route_row
        src = self.cur.execute(
            """SELECT l.load_id, l.customer_id, c.customer_name, l.load_type, l.weight_lbs,
                      l.pieces, l.revenue, l.fuel_surcharge, l.accessorial_charges, l.booking_type
               FROM loads l JOIN customers c ON c.customer_id = l.customer_id
               WHERE l.route_id = ? AND l.load_date >= '2024-06-01'
               ORDER BY l.load_id LIMIT 40""",
            (route_id,),
        ).fetchall()
        row = self.rng.choice(src)
        self._load_seq += 1
        pickup_fid = self.facility.get((oc, os_), ("CUSTDOCK-" + oc[:3].upper(), *self.coords[(oc, os_)]))[0]
        dest_fid = self.facility.get((dc, ds), ("CUSTDOCK-" + dc[:3].upper(), *self.coords[(dc, ds)]))[0]
        transit_hours = dist / PLANNING_MPH + DOCK_BUFFER_HOURS
        return LiveLoad(
            load_id=f"L-{self.t0:%y%m}-{self._load_seq:03d}",
            source_load_id=row[0],
            customer_id=row[1],
            customer_name=row[2],
            route_id=route_id,
            origin_city=oc, origin_state=os_,
            dest_city=dc, dest_state=ds,
            pickup_facility_id=pickup_fid,
            dest_facility_id=dest_fid,
            load_type=row[3],
            weight_lbs=row[4],
            pieces=row[5],
            revenue=row[6],
            fuel_surcharge=row[7],
            accessorial_charges=row[8],
            booking_type=row[9],
            distance_miles=dist,
            pickup_window_start=pickup_start,
            pickup_window_end=pickup_start + timedelta(hours=2),
            delivery_deadline=pickup_start + timedelta(hours=transit_hours + 2),
            status=status,
        )

    # ---- trips ---------------------------------------------------------------
    def make_trip(
        self,
        load: LiveLoad,
        driver: FleetDriver,
        truck: FleetTruck,
        progress_frac: float,
        status: TripStatus,
        fault: dict | None = None,
    ) -> tuple[LiveTrip, list[HosEvent]]:
        """Returns the trip plus the FMCSA-legal duty history that produced it."""
        self._trip_seq += 1
        o = (load.origin_city, load.origin_state)
        d = (load.dest_city, load.dest_state)
        geom = self.geometry(o, d)
        line = Polyline.from_points(json.loads(geom.encoded_polyline))
        total = line.total_miles
        progress = total * progress_frac
        drive_min_done = int(progress / LINEHAUL_BASE_MPH * 60)

        duty_events = [
            HosEvent(driver_id=driver.driver_id, duty=duty, start=s, end=e)
            for duty, s, e in schedule_events(drive_min_done, self.t0)
        ] if status != TripStatus.AT_PICKUP else []
        started_at = (duty_events[0].start if duty_events
                      else self.t0 - timedelta(minutes=100 + 25))

        plan_drive_min = int(total / PLANNING_MPH * 60)
        planned_eta = started_at + timedelta(
            minutes=25 + legal_elapsed_minutes(plan_drive_min)
        ) + timedelta(hours=DOCK_BUFFER_HOURS)
        load.pickup_window_start = started_at - timedelta(hours=1)
        load.pickup_window_end = started_at + timedelta(hours=1)
        load.delivery_deadline = planned_eta + timedelta(hours=2)

        trip = LiveTrip(
            trip_id=f"T-{self.t0:%y%m}-{self._trip_seq:03d}",
            load_id=load.load_id,
            driver_id=driver.driver_id,
            truck_id=truck.truck_id,
            status=status,
            geometry_id=geom.id,
            planned_eta=planned_eta,
            started_at=started_at,
            progress_miles=round(progress, 1),
            total_miles=round(total, 1),
            speed_ewma_mph=LINEHAUL_BASE_MPH,
            eta_state=EtaState.NORMAL,
            last_ping_at=self.t0,
            fault_script=json.dumps(fault or {}),
        )

        # the walker always leaves an open DRIVING block at t0
        driver.duty = (
            DriverDuty.DRIVING
            if status in (TripStatus.IN_TRANSIT, TripStatus.EN_ROUTE_PICKUP)
            else DriverDuty.ON_DUTY
        )

        lat, lon, heading = line.point_at(progress)
        truck.lat, truck.lon, truck.heading_deg = lat, lon, heading
        truck.speed_mph = LINEHAUL_BASE_MPH if status == TripStatus.IN_TRANSIT else 0.0
        truck.driver_id = driver.driver_id
        truck.trip_id = trip.trip_id
        driver.lat, driver.lon = lat, lon
        driver.truck_id = truck.truck_id
        driver.trip_id = trip.trip_id
        if status == TripStatus.AT_PICKUP:
            trip.dwell_facility_id = load.pickup_facility_id
            trip.dwell_started_at = self.t0 - timedelta(minutes=100)
            duty_events = [HosEvent(
                driver_id=driver.driver_id, duty=DriverDuty.ON_DUTY,
                start=trip.dwell_started_at, end=None)]
        load.status = LoadStatus.IN_TRANSIT if status == TripStatus.IN_TRANSIT else LoadStatus.ASSIGNED
        return trip, duty_events

    # ---- HOS history ----------------------------------------------------------
    def seed_hos(
        self, drivers: list[FleetDriver], busy_since: dict[str, datetime]
    ) -> list[HosEvent]:
        """Plausible prior-days duty history per driver.

        Days are only generated when the full day block ends >= 10h before the
        driver's current trip history begins, so the ledger never sees
        overlapping duty and every driver is violation-free at t0.
        """
        events: list[HosEvent] = []
        day0 = self.t0 - timedelta(days=8)
        for i, drv in enumerate(drivers):
            rng = random.Random(SEED * 1000 + i)
            cutoff = busy_since.get(drv.driver_id, self.t0)
            for day in range(8):
                base = day0 + timedelta(days=day)
                if rng.random() < 0.25:
                    continue  # day off
                start_hour = rng.uniform(5.5, 7.5)
                drive_h = rng.uniform(5.0, 8.5)
                duty_start = base + timedelta(hours=start_hour)
                pre = rng.uniform(0.4, 0.8)
                day_end = duty_start + timedelta(hours=pre + drive_h + 0.6)
                if day_end + timedelta(hours=10) >= cutoff:
                    continue
                events.append(HosEvent(
                    driver_id=drv.driver_id, duty=DriverDuty.ON_DUTY,
                    start=duty_start, end=duty_start + timedelta(hours=pre)))
                d1 = drive_h / 2
                s1 = duty_start + timedelta(hours=pre)
                events.append(HosEvent(
                    driver_id=drv.driver_id, duty=DriverDuty.DRIVING,
                    start=s1, end=s1 + timedelta(hours=d1)))
                brk = s1 + timedelta(hours=d1)
                events.append(HosEvent(
                    driver_id=drv.driver_id, duty=DriverDuty.OFF,
                    start=brk, end=brk + timedelta(minutes=35)))
                s2 = brk + timedelta(minutes=35)
                events.append(HosEvent(
                    driver_id=drv.driver_id, duty=DriverDuty.DRIVING,
                    start=s2, end=s2 + timedelta(hours=drive_h - d1)))
        return events

    def top_up_cycle(
        self,
        driver_id: str,
        events: list[HosEvent],
        busy_since: datetime,
        target_cycle_min: int,
    ) -> list[HosEvent]:
        """Adds early-morning ON_DUTY yard blocks on free prior days until the
        driver's 70h/8d recap reaches the target — the dispatch squeeze story,
        built without ever violating."""
        mine = [e for e in events if e.driver_id == driver_id]
        extra: list[HosEvent] = []
        for day in range(1, 8):
            clocks = compute_clocks(mine + extra, self.t0)
            deficit = target_cycle_min - clocks.cycle_min_used
            if deficit <= 0:
                break
            base = self.t0 - timedelta(days=day)
            start = base.replace(hour=1, minute=30)
            end = start + timedelta(minutes=min(deficit, 5 * 60))
            if end + timedelta(hours=10) >= busy_since:
                continue
            if any(e.start <= end and (e.end or self.t0) >= start for e in mine + extra):
                continue
            extra.append(HosEvent(
                driver_id=driver_id, duty=DriverDuty.ON_DUTY, start=start, end=end))
        return extra


def build_world(conn: sqlite3.Connection, t0: datetime) -> dict:
    with Session(engine) as session:
        wb = WorldBuilder(conn, session, t0)
        trucks, drivers = wb.carve_fleet()
        routes = wb._fleet_routes()
        rng = wb.rng

        outbound = [r for r in routes if r[1] in FLEET_TERMINALS]
        by_origin: dict[str, list[tuple]] = {}
        for r in outbound:
            by_origin.setdefault(r[1], []).append(r)

        active_trucks = [t for t in trucks if t.status == "Active"]
        available_drivers = sorted(drivers, key=lambda d: d.driver_id)

        # Deterministic pairings: i-th active truck with i-th driver from same
        # terminal where possible, falling back to any unassigned driver.
        pairs: list[tuple[FleetTruck, FleetDriver]] = []
        used: set[str] = set()
        for truck in active_trucks:
            pick = next(
                (d for d in available_drivers
                 if d.driver_id not in used and d.home_terminal == truck.home_terminal),
                None,
            ) or next((d for d in available_drivers if d.driver_id not in used), None)
            if pick:
                used.add(pick.driver_id)
                pairs.append((truck, pick))

        # ---- fault scripts (detected honestly by the watchdog) ----------------
        faults: list[dict | None] = [
            {"type": "dark", "at_progress": 0.47, "duration_min": 75},
            {"type": "slowdown", "from": 0.50, "to": 0.78, "factor": 0.42},
            {"type": "offset", "from": 0.52, "to": 0.70, "offset_mi": 3.6},
            None, None, None, None, None,
        ]

        loads: list[LiveLoad] = []
        trips: list[LiveTrip] = []
        trip_events: list[HosEvent] = []

        # 8 linehaul trips in motion at T0, staggered along their routes
        progress_fracs = [0.42, 0.44, 0.48, 0.55, 0.30, 0.66, 0.18, 0.74]
        route_cycle = outbound * 3
        for i, frac in enumerate(progress_fracs):
            truck, driver = pairs[i]
            route = route_cycle[i * 2 + 1]
            load = wb.make_load(route, wb.t0 - timedelta(hours=6), LoadStatus.ASSIGNED)
            trip, events = wb.make_trip(load, driver, truck, frac,
                                        TripStatus.IN_TRANSIT, faults[i])
            loads.append(load)
            trips.append(trip)
            trip_events.extend(events)

        # 1 truck dwelling at a pickup dock (detention builds up)
        truck, driver = pairs[8]
        home_routes = by_origin.get(truck.home_terminal) or outbound
        load = wb.make_load(rng.choice(home_routes), wb.t0 - timedelta(hours=2), LoadStatus.ASSIGNED)
        trip, events = wb.make_trip(load, driver, truck, 0.0, TripStatus.AT_PICKUP,
                                    {"type": "dwell", "extra_min": 200})
        loads.append(load)
        trips.append(trip)
        trip_events.extend(events)

        # 6 unassigned loads for the dispatch board
        unassigned_routes = rng.sample(outbound, min(6, len(outbound)))
        for i, route in enumerate(unassigned_routes):
            loads.append(wb.make_load(
                route,
                wb.t0 + timedelta(hours=2 + 3 * i),
                LoadStatus.UNASSIGNED,
            ))

        # prior-days history that never overlaps live trip duty
        busy_since = {}
        for ev in trip_events:
            cur = busy_since.get(ev.driver_id)
            busy_since[ev.driver_id] = min(cur, ev.start) if cur else ev.start
        hos_events = wb.seed_hos(drivers, busy_since) + trip_events

        # the driver of the longest in-flight trip runs a nearly spent 70h cycle
        squeeze_driver = trips[2].driver_id
        hos_events += wb.top_up_cycle(
            squeeze_driver, hos_events,
            busy_since.get(squeeze_driver, wb.t0), target_cycle_min=66 * 60)

        # Compliance faults: one truck overdue for PM, one inspection expiring
        idle_trucks = [t for t in active_trucks if t.trip_id is None]
        if idle_trucks:
            idle_trucks[0].last_pm_date = t0 - timedelta(days=PM_INTERVAL_DAYS + 4)
            idle_trucks[0].next_pm_due = idle_trucks[0].last_pm_date + timedelta(days=PM_INTERVAL_DAYS)
        overdue_pm_truck = idle_trucks[0].truck_id if idle_trucks else None
        busy = [t for t in active_trucks if t.trip_id is not None]
        busy[-1].annual_inspection_expiry = t0 + timedelta(days=5)

        session.add_all(trucks)
        session.add_all(drivers)
        session.add_all(loads)
        session.add_all(trips)
        session.add_all(hos_events)
        session.add(SimState(id=1, t0=t0, sim_now=t0, speed=SIM_SPEED_DEFAULT, running=True))
        session.commit()

        return {
            "trucks": len(trucks),
            "drivers": len(drivers),
            "loads": len(loads),
            "active_trips": len(trips),
            "hos_events": len(hos_events),
            "squeeze_driver": squeeze_driver,
            "overdue_pm_truck": overdue_pm_truck,
            "geometries": len(wb.geometry_ids),
        }
