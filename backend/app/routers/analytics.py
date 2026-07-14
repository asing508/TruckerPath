"""Cost intelligence: computed KPIs + CPM decomposition + ask-your-fleet."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from ..agents import analyst
from ..db import raw_connection

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_background: set[asyncio.Task] = set()


@router.get("/kpis")
def kpis(year: str = "2024") -> dict:
    conn = raw_connection()
    row = conn.execute(
        """SELECT SUM(total_miles), SUM(revenue), SUM(fuel_cost), SUM(maintenance_cost),
                  SUM(loads_count)
           FROM cost_summary_monthly WHERE month LIKE ?""", (f"{year}%",)).fetchone()
    miles, revenue, fuel, maint, loads = (v or 0 for v in row)
    detention = conn.execute(
        """SELECT AVG(detention_minutes), SUM(CASE WHEN detention_minutes > 120 THEN 1 ELSE 0 END)
           FROM delivery_events WHERE substr(scheduled_datetime,1,4) = ?""", (year,)).fetchone()
    otd = conn.execute(
        """SELECT AVG(on_time_flag) FROM delivery_events
           WHERE event_type='Delivery' AND substr(scheduled_datetime,1,4) = ?""", (year,)).fetchone()
    deadhead = conn.execute(
        """SELECT AVG(d.deadhead_miles) FROM trip_deadhead d
           JOIN trips t ON t.trip_id = d.trip_id
           WHERE substr(t.dispatch_date,1,4) = ? AND d.deadhead_miles > 0""", (year,)).fetchone()
    conn.close()
    cost = fuel + maint
    return {
        "year": year,
        "total_miles": miles,
        "revenue": revenue,
        "fuel_cost": fuel,
        "maintenance_cost": maint,
        "cost_per_mile": round(cost / miles, 3) if miles else None,
        "revenue_per_mile": round(revenue / miles, 3) if miles else None,
        "loads": loads,
        "on_time_rate": round(otd[0] or 0, 3),
        "avg_detention_min": round(detention[0] or 0, 1),
        "detention_events_over_2h": detention[1],
        "avg_deadhead_miles": round(deadhead[0] or 0, 1),
    }


@router.get("/monthly")
def monthly() -> list[dict]:
    conn = raw_connection()
    rows = conn.execute(
        """SELECT month, total_miles, revenue, fuel_cost, maintenance_cost, loads_count
           FROM cost_summary_monthly ORDER BY month""").fetchall()
    conn.close()
    return [{
        "month": r[0], "miles": r[1], "revenue": r[2], "fuel_cost": r[3] or 0,
        "maintenance_cost": r[4] or 0,
        "cpm": round((r[3] or 0) / r[1], 3) if r[1] else None,
        "rpm": round(r[2] / r[1], 3) if r[1] else None,
        "loads": r[5],
    } for r in rows]


@router.get("/cpm")
def cpm(by: str = "driver", year: str = "2024", limit: int = 12) -> list[dict]:
    conn = raw_connection()
    if by == "driver":
        sql = """
            SELECT s.name AS label,
                   SUM(t.actual_distance_miles) AS miles,
                   SUM(l.revenue) AS revenue,
                   SUM(t.fuel_gallons_used * fp.avg_price) AS fuel_cost,
                   AVG(e.on_time) AS on_time
            FROM trips t
            JOIN loads l ON l.load_id = t.load_id
            JOIN driver_stats s ON s.driver_id = t.driver_id
            LEFT JOIN (SELECT month, AVG(avg_price_per_gallon) avg_price
                       FROM fuel_price_state_month GROUP BY month) fp
                   ON fp.month = substr(t.dispatch_date,1,7)
            LEFT JOIN (SELECT trip_id, AVG(on_time_flag) on_time
                       FROM delivery_events GROUP BY trip_id) e
                   ON e.trip_id = t.trip_id
            WHERE substr(t.dispatch_date,1,4) = ?
            GROUP BY t.driver_id HAVING miles > 10000
            ORDER BY fuel_cost / miles DESC LIMIT ?"""
    elif by == "lane":
        sql = """
            SELECT ls.lane AS label,
                   SUM(t.actual_distance_miles) AS miles,
                   SUM(l.revenue) AS revenue,
                   SUM(t.fuel_gallons_used * fp.avg_price) AS fuel_cost,
                   AVG(ls.on_time_rate) AS on_time
            FROM trips t
            JOIN loads l ON l.load_id = t.load_id
            JOIN lane_stats ls ON ls.route_id = l.route_id
            LEFT JOIN (SELECT month, AVG(avg_price_per_gallon) avg_price
                       FROM fuel_price_state_month GROUP BY month) fp
                   ON fp.month = substr(t.dispatch_date,1,7)
            WHERE substr(t.dispatch_date,1,4) = ?
            GROUP BY l.route_id HAVING miles > 50000
            ORDER BY fuel_cost / miles DESC LIMIT ?"""
    else:  # customer
        sql = """
            SELECT c.customer_name AS label,
                   SUM(t.actual_distance_miles) AS miles,
                   SUM(l.revenue) AS revenue,
                   SUM(t.fuel_gallons_used * fp.avg_price) AS fuel_cost,
                   AVG(e.on_time) AS on_time
            FROM trips t
            JOIN loads l ON l.load_id = t.load_id
            JOIN customers c ON c.customer_id = l.customer_id
            LEFT JOIN (SELECT month, AVG(avg_price_per_gallon) avg_price
                       FROM fuel_price_state_month GROUP BY month) fp
                   ON fp.month = substr(t.dispatch_date,1,7)
            LEFT JOIN (SELECT trip_id, AVG(on_time_flag) on_time
                       FROM delivery_events GROUP BY trip_id) e
                   ON e.trip_id = t.trip_id
            WHERE substr(t.dispatch_date,1,4) = ?
            GROUP BY l.customer_id HAVING miles > 50000
            ORDER BY revenue DESC LIMIT ?"""
    rows = conn.execute(sql, (year, limit)).fetchall()
    conn.close()
    return [{
        "label": r[0], "miles": r[1], "revenue": r[2],
        "fuel_cost": round(r[3] or 0, 0),
        "fuel_cpm": round((r[3] or 0) / r[1], 3) if r[1] else None,
        "rpm": round(r[2] / r[1], 3) if r[1] else None,
        "margin_per_mile": round((r[2] - (r[3] or 0)) / r[1], 3) if r[1] else None,
        "on_time_rate": round(r[4] or 0, 3),
    } for r in rows]


class AskBody(BaseModel):
    question: str


@router.post("/ask")
async def ask(body: AskBody) -> dict:
    task = asyncio.create_task(analyst.ask(body.question))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"started": True}
