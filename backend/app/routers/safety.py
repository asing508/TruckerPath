"""Safety & compliance board + coaching briefs."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from sqlmodel import Session, select

from ..agents import safety as safety_agent
from ..agents.safety import compute_risk_board
from ..db import engine
from ..models import FleetTruck, SimState

router = APIRouter(prefix="/api/safety", tags=["safety"])

_background: set[asyncio.Task] = set()


@router.get("/board")
def board() -> dict:
    with Session(engine) as s:
        now = s.get(SimState, 1).sim_now
        trucks = s.exec(select(FleetTruck)).all()
        equipment = [{
            "truck_id": t.truck_id, "unit": t.unit_number, "make": t.make,
            "model_year": t.model_year, "status": t.status,
            "terminal": t.home_terminal,
            "last_pm": t.last_pm_date, "next_pm_due": t.next_pm_due,
            "pm_overdue_days": max(0, (now - t.next_pm_due).days),
            "inspection_expiry": t.annual_inspection_expiry,
            "inspection_days_left": (t.annual_inspection_expiry - now).days,
            "odometer": round(t.odometer_miles),
        } for t in trucks]
    return {"drivers": compute_risk_board(), "equipment": equipment}


@router.post("/brief/{driver_id}")
async def brief(driver_id: str) -> dict:
    task = asyncio.create_task(safety_agent.coaching_brief(driver_id))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"started": True}
