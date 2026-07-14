"""CSV → SQLite warehouse loader + derived analytical tables.

Loads the 14 Kaggle CSVs verbatim (typed), then derives the stat tables the
dispatch scorer, cost dashboard, and NL->SQL agent rely on:

  driver_stats        per-driver career features
  lane_stats          per-route service history (transit, on-time, detention)
  fuel_price_state_month
  cost_summary_monthly
  trip_deadhead       est. empty miles before each trip (prev dest -> origin)
  city_coords         city centroid lookup used across the app
"""
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

from ..config import ARCHIVE_DIR, EXTRA_CITY_COORDS
from ..geo import haversine_miles

# (csv file, table, [(column, type)]) — TEXT unless stated; *_flag → INTEGER 0/1
TABLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("drivers.csv", "drivers", [
        ("driver_id", "TEXT PRIMARY KEY"), ("first_name", "TEXT"), ("last_name", "TEXT"),
        ("hire_date", "TEXT"), ("termination_date", "TEXT"), ("license_number", "TEXT"),
        ("license_state", "TEXT"), ("date_of_birth", "TEXT"), ("home_terminal", "TEXT"),
        ("employment_status", "TEXT"), ("cdl_class", "TEXT"), ("years_experience", "INTEGER"),
    ]),
    ("trucks.csv", "trucks", [
        ("truck_id", "TEXT PRIMARY KEY"), ("unit_number", "TEXT"), ("make", "TEXT"),
        ("model_year", "INTEGER"), ("vin", "TEXT"), ("acquisition_date", "TEXT"),
        ("acquisition_mileage", "INTEGER"), ("fuel_type", "TEXT"),
        ("tank_capacity_gallons", "INTEGER"), ("status", "TEXT"), ("home_terminal", "TEXT"),
    ]),
    ("trailers.csv", "trailers", [
        ("trailer_id", "TEXT PRIMARY KEY"), ("trailer_number", "TEXT"), ("trailer_type", "TEXT"),
        ("length_feet", "INTEGER"), ("model_year", "INTEGER"), ("vin", "TEXT"),
        ("acquisition_date", "TEXT"), ("status", "TEXT"), ("current_location", "TEXT"),
    ]),
    ("customers.csv", "customers", [
        ("customer_id", "TEXT PRIMARY KEY"), ("customer_name", "TEXT"), ("customer_type", "TEXT"),
        ("credit_terms_days", "INTEGER"), ("primary_freight_type", "TEXT"),
        ("account_status", "TEXT"), ("contract_start_date", "TEXT"),
        ("annual_revenue_potential", "REAL"),
    ]),
    ("facilities.csv", "facilities", [
        ("facility_id", "TEXT PRIMARY KEY"), ("facility_name", "TEXT"), ("facility_type", "TEXT"),
        ("city", "TEXT"), ("state", "TEXT"), ("latitude", "REAL"), ("longitude", "REAL"),
        ("dock_doors", "INTEGER"), ("operating_hours", "TEXT"),
    ]),
    ("routes.csv", "routes", [
        ("route_id", "TEXT PRIMARY KEY"), ("origin_city", "TEXT"), ("origin_state", "TEXT"),
        ("destination_city", "TEXT"), ("destination_state", "TEXT"),
        ("typical_distance_miles", "REAL"), ("base_rate_per_mile", "REAL"),
        ("fuel_surcharge_rate", "REAL"), ("typical_transit_days", "INTEGER"),
    ]),
    ("loads.csv", "loads", [
        ("load_id", "TEXT PRIMARY KEY"), ("customer_id", "TEXT"), ("route_id", "TEXT"),
        ("load_date", "TEXT"), ("load_type", "TEXT"), ("weight_lbs", "INTEGER"),
        ("pieces", "INTEGER"), ("revenue", "REAL"), ("fuel_surcharge", "REAL"),
        ("accessorial_charges", "REAL"), ("load_status", "TEXT"), ("booking_type", "TEXT"),
    ]),
    ("trips.csv", "trips", [
        ("trip_id", "TEXT PRIMARY KEY"), ("load_id", "TEXT"), ("driver_id", "TEXT"),
        ("truck_id", "TEXT"), ("trailer_id", "TEXT"), ("dispatch_date", "TEXT"),
        ("actual_distance_miles", "REAL"), ("actual_duration_hours", "REAL"),
        ("fuel_gallons_used", "REAL"), ("average_mpg", "REAL"), ("idle_time_hours", "REAL"),
        ("trip_status", "TEXT"),
    ]),
    ("fuel_purchases.csv", "fuel_purchases", [
        ("fuel_purchase_id", "TEXT PRIMARY KEY"), ("trip_id", "TEXT"), ("truck_id", "TEXT"),
        ("driver_id", "TEXT"), ("purchase_date", "TEXT"), ("location_city", "TEXT"),
        ("location_state", "TEXT"), ("gallons", "REAL"), ("price_per_gallon", "REAL"),
        ("total_cost", "REAL"), ("fuel_card_number", "TEXT"),
    ]),
    ("maintenance_records.csv", "maintenance_records", [
        ("maintenance_id", "TEXT PRIMARY KEY"), ("truck_id", "TEXT"), ("maintenance_date", "TEXT"),
        ("maintenance_type", "TEXT"), ("odometer_reading", "INTEGER"), ("labor_hours", "REAL"),
        ("labor_cost", "REAL"), ("parts_cost", "REAL"), ("total_cost", "REAL"),
        ("facility_location", "TEXT"), ("downtime_hours", "REAL"), ("service_description", "TEXT"),
    ]),
    ("delivery_events.csv", "delivery_events", [
        ("event_id", "TEXT PRIMARY KEY"), ("load_id", "TEXT"), ("trip_id", "TEXT"),
        ("event_type", "TEXT"), ("facility_id", "TEXT"), ("scheduled_datetime", "TEXT"),
        ("actual_datetime", "TEXT"), ("detention_minutes", "INTEGER"), ("on_time_flag", "INTEGER"),
        ("location_city", "TEXT"), ("location_state", "TEXT"),
    ]),
    ("safety_incidents.csv", "safety_incidents", [
        ("incident_id", "TEXT PRIMARY KEY"), ("trip_id", "TEXT"), ("truck_id", "TEXT"),
        ("driver_id", "TEXT"), ("incident_date", "TEXT"), ("incident_type", "TEXT"),
        ("location_city", "TEXT"), ("location_state", "TEXT"), ("at_fault_flag", "INTEGER"),
        ("injury_flag", "INTEGER"), ("vehicle_damage_cost", "REAL"), ("cargo_damage_cost", "REAL"),
        ("claim_amount", "REAL"), ("preventable_flag", "INTEGER"), ("description", "TEXT"),
    ]),
    ("driver_monthly_metrics.csv", "driver_monthly_metrics", [
        ("driver_id", "TEXT"), ("month", "TEXT"), ("trips_completed", "INTEGER"),
        ("total_miles", "REAL"), ("total_revenue", "REAL"), ("average_mpg", "REAL"),
        ("total_fuel_gallons", "REAL"), ("on_time_delivery_rate", "REAL"),
        ("average_idle_hours", "REAL"),
    ]),
    ("truck_utilization_metrics.csv", "truck_utilization_metrics", [
        ("truck_id", "TEXT"), ("month", "TEXT"), ("trips_completed", "INTEGER"),
        ("total_miles", "REAL"), ("total_revenue", "REAL"), ("average_mpg", "REAL"),
        ("maintenance_events", "INTEGER"), ("maintenance_cost", "REAL"),
        ("downtime_hours", "REAL"), ("utilization_rate", "REAL"),
    ]),
]

INDICES = [
    "CREATE INDEX IF NOT EXISTS ix_loads_date ON loads(load_date)",
    "CREATE INDEX IF NOT EXISTS ix_loads_route ON loads(route_id)",
    "CREATE INDEX IF NOT EXISTS ix_loads_customer ON loads(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_trips_load ON trips(load_id)",
    "CREATE INDEX IF NOT EXISTS ix_trips_driver ON trips(driver_id)",
    "CREATE INDEX IF NOT EXISTS ix_trips_truck ON trips(truck_id)",
    "CREATE INDEX IF NOT EXISTS ix_trips_date ON trips(dispatch_date)",
    "CREATE INDEX IF NOT EXISTS ix_fuel_trip ON fuel_purchases(trip_id)",
    "CREATE INDEX IF NOT EXISTS ix_fuel_date ON fuel_purchases(purchase_date)",
    "CREATE INDEX IF NOT EXISTS ix_maint_truck ON maintenance_records(truck_id)",
    "CREATE INDEX IF NOT EXISTS ix_events_trip ON delivery_events(trip_id)",
    "CREATE INDEX IF NOT EXISTS ix_events_load ON delivery_events(load_id)",
    "CREATE INDEX IF NOT EXISTS ix_incidents_driver ON safety_incidents(driver_id)",
]

_BOOL = {"true": 1, "false": 0, "True": 1, "False": 0, "1": 1, "0": 0}


def _coerce(value: str, sql_type: str):
    v = value.strip()
    if v == "":
        return None
    if "INTEGER" in sql_type:
        if v in _BOOL:
            return _BOOL[v]
        return int(float(v))
    if "REAL" in sql_type:
        return float(v)
    return v


def load_csvs(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    cur = conn.cursor()
    for filename, table, columns in TABLES:
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cols_sql = ", ".join(f"{name} {sql_type}" for name, sql_type in columns)
        cur.execute(f"CREATE TABLE {table} ({cols_sql})")
        path: Path = ARCHIVE_DIR / filename
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            names = [c[0] for c in columns]
            types = {c[0]: c[1] for c in columns}
            placeholders = ", ".join("?" for _ in names)
            rows = [
                tuple(_coerce(row[name], types[name]) for name in names)
                for row in reader
            ]
        cur.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        counts[table] = len(rows)
    for ddl in INDICES:
        cur.execute(ddl)
    conn.commit()
    return counts


def build_city_coords(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS city_coords")
    cur.execute("CREATE TABLE city_coords (city TEXT, state TEXT, lat REAL, lon REAL, PRIMARY KEY (city, state))")
    cur.execute("SELECT city, state, AVG(latitude), AVG(longitude) FROM facilities GROUP BY city, state")
    rows = cur.fetchall()
    for (city, state), (lat, lon) in EXTRA_CITY_COORDS.items():
        rows.append((city, state, lat, lon))
    cur.executemany("INSERT OR REPLACE INTO city_coords VALUES (?,?,?,?)", rows)
    conn.commit()


def build_driver_stats(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS driver_stats")
    cur.execute("""
        CREATE TABLE driver_stats AS
        SELECT
            d.driver_id,
            d.first_name || ' ' || d.last_name          AS name,
            d.home_terminal,
            d.employment_status,
            d.years_experience,
            COUNT(t.trip_id)                            AS total_trips,
            COALESCE(SUM(t.actual_distance_miles), 0)   AS total_miles,
            ROUND(AVG(t.average_mpg), 2)                AS avg_mpg,
            ROUND(AVG(t.idle_time_hours), 2)            AS avg_idle_hours,
            ROUND(COALESCE(SUM(l.revenue), 0) / MAX(SUM(t.actual_distance_miles), 1), 3)
                                                        AS revenue_per_mile,
            COALESCE(ot.on_time_rate, 0)                AS on_time_rate,
            COALESCE(inc.n, 0)                          AS incident_count,
            COALESCE(inc.preventable, 0)                AS preventable_incidents
        FROM drivers d
        LEFT JOIN trips t   ON t.driver_id = d.driver_id
        LEFT JOIN loads l   ON l.load_id = t.load_id
        LEFT JOIN (
            SELECT t.driver_id, AVG(e.on_time_flag) AS on_time_rate
            FROM delivery_events e JOIN trips t ON t.trip_id = e.trip_id
            WHERE e.event_type = 'Delivery'
            GROUP BY t.driver_id
        ) ot ON ot.driver_id = d.driver_id
        LEFT JOIN (
            SELECT driver_id, COUNT(*) AS n, SUM(preventable_flag) AS preventable
            FROM safety_incidents GROUP BY driver_id
        ) inc ON inc.driver_id = d.driver_id
        GROUP BY d.driver_id
    """)
    conn.commit()


def build_lane_stats(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS lane_stats")
    cur.execute("""
        CREATE TABLE lane_stats (
            route_id TEXT PRIMARY KEY,
            lane TEXT,
            trips_count INTEGER,
            avg_transit_hours REAL,
            on_time_rate REAL,
            avg_detention_min REAL,
            p90_detention_min REAL,
            avg_revenue REAL,
            revenue_per_mile REAL
        )
    """)
    cur.execute("""
        SELECT l.route_id,
               r.origin_city || ', ' || r.origin_state || ' -> ' ||
               r.destination_city || ', ' || r.destination_state,
               COUNT(DISTINCT t.trip_id),
               AVG(t.actual_duration_hours),
               AVG(CASE WHEN e.event_type = 'Delivery' THEN e.on_time_flag END),
               AVG(e.detention_minutes),
               NULL,
               AVG(l.revenue),
               AVG(l.revenue) / MAX(AVG(t.actual_distance_miles), 1)
        FROM loads l
        JOIN routes r ON r.route_id = l.route_id
        JOIN trips t ON t.load_id = l.load_id
        LEFT JOIN delivery_events e ON e.trip_id = t.trip_id
        GROUP BY l.route_id
    """)
    base = cur.fetchall()

    detentions: dict[str, list[int]] = defaultdict(list)
    cur.execute("""
        SELECT l.route_id, e.detention_minutes
        FROM delivery_events e JOIN loads l ON l.load_id = e.load_id
        WHERE e.detention_minutes IS NOT NULL
    """)
    for route_id, minutes in cur.fetchall():
        detentions[route_id].append(minutes)

    rows = []
    for r in base:
        vals = sorted(detentions.get(r[0], []))
        p90 = vals[int(len(vals) * 0.9)] if vals else None
        rows.append((r[0], r[1], r[2], round(r[3] or 0, 1), round(r[4] or 0, 3),
                     round(r[5] or 0, 1), p90, round(r[7] or 0, 2), round(r[8] or 0, 3)))
    cur.executemany("INSERT INTO lane_stats VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()


def build_fuel_and_cost_summaries(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS fuel_price_state_month")
    cur.execute("""
        CREATE TABLE fuel_price_state_month AS
        SELECT location_state AS state,
               substr(purchase_date, 1, 7) AS month,
               ROUND(AVG(price_per_gallon), 3) AS avg_price_per_gallon,
               ROUND(SUM(gallons), 1) AS total_gallons,
               ROUND(SUM(total_cost), 2) AS total_cost
        FROM fuel_purchases
        GROUP BY location_state, substr(purchase_date, 1, 7)
    """)
    cur.execute("DROP TABLE IF EXISTS cost_summary_monthly")
    cur.execute("""
        CREATE TABLE cost_summary_monthly AS
        SELECT m.month,
               m.total_miles,
               m.revenue,
               f.fuel_cost,
               COALESCE(mt.maintenance_cost, 0) AS maintenance_cost,
               m.loads_count
        FROM (
            SELECT substr(t.dispatch_date, 1, 7) AS month,
                   SUM(t.actual_distance_miles) AS total_miles,
                   SUM(l.revenue) AS revenue,
                   COUNT(*) AS loads_count
            FROM trips t JOIN loads l ON l.load_id = t.load_id
            GROUP BY substr(t.dispatch_date, 1, 7)
        ) m
        LEFT JOIN (
            SELECT substr(purchase_date, 1, 7) AS month, SUM(total_cost) AS fuel_cost
            FROM fuel_purchases GROUP BY substr(purchase_date, 1, 7)
        ) f ON f.month = m.month
        LEFT JOIN (
            SELECT substr(maintenance_date, 1, 7) AS month, SUM(total_cost) AS maintenance_cost
            FROM maintenance_records GROUP BY substr(maintenance_date, 1, 7)
        ) mt ON mt.month = m.month
    """)
    conn.commit()


def build_trip_deadhead(conn: sqlite3.Connection) -> None:
    """Empty-mile estimate per trip: previous trip's destination -> this origin.

    Sorted per truck by dispatch date; O(n log n) total. City centroids come
    from city_coords, so the estimate is honest about being city-level.
    """
    cur = conn.cursor()
    coords = {(c, s): (lat, lon) for c, s, lat, lon in
              cur.execute("SELECT city, state, lat, lon FROM city_coords")}
    cur.execute("""
        SELECT t.trip_id, t.truck_id, t.dispatch_date,
               r.origin_city, r.origin_state, r.destination_city, r.destination_state
        FROM trips t
        JOIN loads l ON l.load_id = t.load_id
        JOIN routes r ON r.route_id = l.route_id
        WHERE t.truck_id != ''
        ORDER BY t.truck_id, t.dispatch_date, t.trip_id
    """)
    rows = cur.fetchall()
    out: list[tuple[str, float]] = []
    prev_truck = None
    prev_dest: tuple[str, str] | None = None
    for trip_id, truck_id, _, oc, os_, dc, ds in rows:
        if truck_id != prev_truck:
            prev_truck, prev_dest = truck_id, None
        dead = 0.0
        if prev_dest and prev_dest in coords and (oc, os_) in coords:
            (plat, plon), (olat, olon) = coords[prev_dest], coords[(oc, os_)]
            dead = round(haversine_miles(plat, plon, olat, olon), 1)
        out.append((trip_id, dead))
        prev_dest = (dc, ds)
    cur.execute("DROP TABLE IF EXISTS trip_deadhead")
    cur.execute("CREATE TABLE trip_deadhead (trip_id TEXT PRIMARY KEY, deadhead_miles REAL)")
    cur.executemany("INSERT INTO trip_deadhead VALUES (?,?)", out)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_deadhead ON trip_deadhead(trip_id)")
    conn.commit()


def build_warehouse(conn: sqlite3.Connection) -> dict[str, int]:
    counts = load_csvs(conn)
    build_city_coords(conn)
    build_driver_stats(conn)
    build_lane_stats(conn)
    build_fuel_and_cost_summaries(conn)
    build_trip_deadhead(conn)
    return counts
