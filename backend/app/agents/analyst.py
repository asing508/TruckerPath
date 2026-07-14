"""Cost Analyst: natural language -> guarded SQL over the warehouse.

The run_sql tool executes on a read-only SQLite connection with an authorizer
(SELECT-only, sensitive tables denied) plus a progress-handler timeout and a
row cap, so arbitrary model-written SQL is safe by construction.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from ..db import readonly_connection
from .gemini import Tool, run_agent, tool
from .schemas import AnalystAnswer

ROW_CAP = 120
PROGRESS_OPS_BUDGET = 4_000_000  # VM steps before we abort a runaway query

HIDDEN_TABLES = {"doc_packets", "agent_runs", "agent_steps", "pending_actions",
                 "message_log", "invoices", "sqlite_sequence"}

TABLE_NOTES = {
    "loads": "one row per shipment: revenue, fuel_surcharge, accessorial_charges, booking_type, load_date",
    "trips": "execution of a load: driver_id, truck_id, actual_distance_miles, fuel_gallons_used, average_mpg, idle_time_hours",
    "delivery_events": "pickup+delivery per load: scheduled vs actual datetimes, detention_minutes, on_time_flag (1/0)",
    "fuel_purchases": "every fuel transaction: gallons, price_per_gallon, total_cost, location_state, purchase_date",
    "maintenance_records": "service history per truck: maintenance_type, total_cost, downtime_hours",
    "safety_incidents": "accidents/violations: incident_type, preventable_flag, claim_amount",
    "driver_stats": "derived per-driver career stats: on_time_rate, revenue_per_mile, incident_count",
    "lane_stats": "derived per-route stats: avg_transit_hours, on_time_rate, detention norms, revenue_per_mile",
    "cost_summary_monthly": "derived: month, total_miles, revenue, fuel_cost, maintenance_cost, loads_count",
    "fuel_price_state_month": "derived: avg diesel price by state and month",
    "trip_deadhead": "derived: estimated empty miles before each trip",
    "city_coords": "city centroid lookup",
    "fleet_drivers": "LIVE fleet drivers incl. current HOS clock snapshots",
    "fleet_trucks": "LIVE fleet trucks incl. PM due dates",
    "live_loads": "LIVE loads on the board right now",
    "live_trips": "LIVE trips in motion right now",
}


@lru_cache(maxsize=1)
def schema_reference() -> str:
    # trusted code path: full connection (the guarded one blocks PRAGMA)
    from ..db import raw_connection
    conn = raw_connection()
    lines = ["SQLite database. Historical warehouse covers 2022-01 .. 2024-12 "
             "(dates are TEXT, ISO). Live tables reflect the current sim. "
             "Money is USD, distance in miles.\n"]
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        if t in HIDDEN_TABLES:
            continue
        cols = [f"{r[1]}" for r in conn.execute(f"PRAGMA table_info({t})")]
        note = TABLE_NOTES.get(t, "")
        lines.append(f"- {t}({', '.join(cols)})" + (f"  // {note}" if note else ""))
    conn.close()
    return "\n".join(lines)


@tool(
    "get_schema",
    "Schema of every queryable table with column names and usage notes. "
    "Call this before writing SQL.",
)
def get_schema() -> str:
    return schema_reference()


@tool(
    "run_sql",
    "Execute one read-only SQLite SELECT and get rows back. Hard limits: "
    "single statement, 120 rows returned. Use aggregate queries, not raw dumps.",
    {"type": "object", "properties": {"sql": {"type": "string"}},
     "required": ["sql"]},
)
def run_sql(sql: str) -> dict:
    conn = readonly_connection()
    budget = [PROGRESS_OPS_BUDGET]

    def watchdog():
        budget[0] -= 1
        return 1 if budget[0] <= 0 else 0

    conn.set_progress_handler(watchdog, 50_000)
    try:
        cur = conn.execute(sql)
        columns = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchmany(ROW_CAP + 1)
        truncated = len(rows) > ROW_CAP
        rows = rows[:ROW_CAP]
        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()


SYSTEM = """You are the cost-intelligence analyst for Sunbelt Carriers, working
over the company's operational warehouse (2022-2024 history) and live fleet
tables. A dispatcher or owner asks questions in plain English.

Method:
1. get_schema first. Think about which tables answer the question.
2. Write focused aggregate SQL (GROUP BY, joins on ids). Multiple run_sql
   calls are fine. Never SELECT * on big tables.
3. Cost-per-mile questions: cost = fuel_purchases.total_cost +
   maintenance_records.total_cost over trips.actual_distance_miles, unless the
   user asks otherwise. State the formula you used.
4. Finalize with a tight answer: the number first, then how it was computed,
   then one actionable observation. Attach a chart when a trend or comparison
   is involved (12 categories max, series values aligned with x).

Rules: every number in the answer must come from run_sql results in this
conversation. If the data cannot answer, say exactly what is missing."""


async def ask(question: str) -> dict:
    result, run_id = await run_agent(
        kind="analyst",
        subject_id=question[:120],
        system=SYSTEM,
        prompt=question,
        tools=[get_schema, run_sql],
        output_schema=AnalystAnswer,
        max_steps=10,
        temperature=0.2,
    )
    if result is None:
        return {"run_id": run_id, "error": "agent failed"}
    return {"run_id": run_id, "answer": result.model_dump()}
