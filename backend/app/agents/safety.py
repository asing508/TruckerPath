"""Safety Sentinel: deterministic risk features + Gemini-written coaching briefs.

The risk board is pure computation (HOS pressure, violations, night-driving
share, incident history, equipment compliance). The LLM's job is judgment and
language: turning a driver's feature vector into a coaching brief a fleet
manager would actually deliver.
"""
from __future__ import annotations

import json
from datetime import timedelta

from sqlmodel import Session, select

from ..config import HOS_CYCLE_LIMIT_MIN
from ..db import engine, raw_connection
from ..models import DriverDuty, FleetDriver, FleetTruck, HosEvent, SimState
from .gemini import run_agent, tool
from .schemas import SafetyBrief


def _night_share(events: list[HosEvent]) -> float:
    """Share of driving minutes between 22:00 and 05:00 over the window."""
    night = total = 0.0
    for e in events:
        if e.duty != DriverDuty.DRIVING or e.end is None:
            continue
        cur = e.start
        while cur < e.end:
            nxt = min(e.end, cur + timedelta(minutes=30))
            mins = (nxt - cur).total_seconds() / 60
            total += mins
            if cur.hour >= 22 or cur.hour < 5:
                night += mins
            cur = nxt
    return round(night / total, 3) if total else 0.0


def compute_risk_board() -> list[dict]:
    with Session(engine) as s:
        now = s.get(SimState, 1).sim_now
        drivers = s.exec(select(FleetDriver)).all()
        events_by_driver: dict[str, list[HosEvent]] = {}
        for ev in s.exec(select(HosEvent)).all():
            events_by_driver.setdefault(ev.driver_id, []).append(ev)
        trucks = {t.driver_id: t for t in s.exec(select(FleetTruck)).all() if t.driver_id}

        conn = raw_connection()
        board = []
        for d in drivers:
            events = events_by_driver.get(d.driver_id, [])
            night = _night_share(events)
            cycle_pressure = d.cycle_min_used / HOS_CYCLE_LIMIT_MIN
            incidents_2y = conn.execute(
                """SELECT COUNT(*), COALESCE(SUM(preventable_flag),0)
                   FROM safety_incidents WHERE driver_id=? AND incident_date >= '2023-01-01'""",
                (d.driver_id,)).fetchone()
            truck = trucks.get(d.driver_id)
            pm_overdue = bool(truck and truck.next_pm_due < now)
            inspection_days = (truck.annual_inspection_expiry - now).days if truck else None

            score = (
                40.0 * cycle_pressure
                + 25.0 * night
                + 8.0 * incidents_2y[0]
                + 6.0 * incidents_2y[1]
                + (12.0 if d.hos_violation_flags else 0.0)
                + (8.0 if pm_overdue else 0.0)
                + (6.0 if inspection_days is not None and inspection_days < 14 else 0.0)
            )
            level = ("SEVERE" if score >= 55 else "ELEVATED" if score >= 35
                     else "GUARDED" if score >= 18 else "LOW")
            board.append({
                "driver_id": d.driver_id,
                "name": d.name,
                "terminal": d.home_terminal,
                "duty": d.duty,
                "risk_score": round(score, 1),
                "risk_level": level,
                "factors": {
                    "cycle_used_pct": round(cycle_pressure * 100, 1),
                    "drive_min_remaining": d.drive_min_remaining_calc(),
                    "window_min_remaining": d.window_min_remaining_calc(),
                    "night_driving_share": night,
                    "active_violations": d.hos_violation_flags or "none",
                    "incidents_since_2023": incidents_2y[0],
                    "preventable_incidents": incidents_2y[1],
                    "truck_pm_overdue": pm_overdue,
                    "inspection_days_left": inspection_days,
                },
            })
        conn.close()
        return sorted(board, key=lambda x: -x["risk_score"])


@tool(
    "get_driver_risk_profile",
    "Computed risk feature vector for one driver: HOS pressure, night share, "
    "violations, incidents, equipment compliance.",
    {"type": "object", "properties": {"driver_id": {"type": "string"}},
     "required": ["driver_id"]},
)
def get_driver_risk_profile(driver_id: str) -> dict:
    for row in compute_risk_board():
        if row["driver_id"] == driver_id:
            return row
    return {"error": "driver not found"}


@tool(
    "get_incident_history",
    "Career incident list for a driver from the safety record.",
    {"type": "object", "properties": {"driver_id": {"type": "string"}},
     "required": ["driver_id"]},
)
def get_incident_history(driver_id: str) -> list[dict]:
    conn = raw_connection()
    rows = conn.execute(
        """SELECT incident_date, incident_type, preventable_flag, claim_amount, description
           FROM safety_incidents WHERE driver_id=? ORDER BY incident_date DESC LIMIT 10""",
        (driver_id,)).fetchall()
    conn.close()
    return [{"date": r[0], "type": r[1], "preventable": bool(r[2]),
             "claim_usd": r[3], "description": r[4]} for r in rows]


SYSTEM = """You are the safety copilot for Sunbelt Carriers. Write a coaching
brief about one driver for the fleet manager.

Method: pull the risk profile, then incident history. Weigh HOS pressure and
fatigue signals (night share, cycle usage) over stale history. Acknowledge
strengths - these briefs go to a human conversation, not a disciplinary file.

Output: risk level consistent with the computed profile unless you argue
otherwise; a brief in 3 short paragraphs (what the data shows, why it matters
this week, what to do about it); 3-5 concrete talking points the manager can
use in a 5-minute check-in. Plain language, no corporate speak, no emojis."""


async def coaching_brief(driver_id: str) -> dict:
    result, run_id = await run_agent(
        kind="safety",
        subject_id=driver_id,
        system=SYSTEM,
        prompt=f"Write the coaching brief for driver {driver_id}.",
        tools=[get_driver_risk_profile, get_incident_history],
        output_schema=SafetyBrief,
        temperature=0.4,
    )
    if result is None:
        return {"run_id": run_id, "error": "agent failed"}
    return {"run_id": run_id, "brief": result.model_dump()}
