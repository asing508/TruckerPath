"""Simulation controls: play / pause / speed / reset."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from ..db import engine, raw_connection
from ..etl.docgen import build_packets
from ..etl.world import build_world
from ..models import (
    AgentRun,
    AgentStep,
    DocPacket,
    FleetDriver,
    FleetException,
    FleetTruck,
    HosEvent,
    Invoice,
    LiveLoad,
    LiveTrip,
    MessageLog,
    PendingAction,
    PingLog,
    RunStatus,
    SimState,
)
from ..sim.engine import sim_engine, snapshot_positions
from ..streams import broadcaster

router = APIRouter(prefix="/api/sim", tags=["sim"])


class SpeedBody(BaseModel):
    speed: int


@router.post("/play")
def play() -> dict:
    state = sim_engine.update_control(running=True)
    broadcaster.publish("tick_control", state)
    return state


@router.post("/pause")
def pause() -> dict:
    state = sim_engine.update_control(running=False)
    broadcaster.publish("tick_control", state)
    return state


@router.post("/speed")
def set_speed(body: SpeedBody) -> dict:
    state = sim_engine.update_control(speed=body.speed)
    broadcaster.publish("tick_control", state)
    return state


@router.post("/reset")
def reset() -> dict:
    """Rebuild the live world from the warehouse (route geometry is kept, so
    no network calls). The demo returns to a deterministic T0."""
    cancelled_run_ids: list[int] = []
    with sim_engine.exclusive_reset():
        with Session(engine) as s:
            # Tell any browser tab holding SSE-cached "RUNNING" agent state to
            # drop it now - the rows are about to disappear, and an in-flight
            # coroutine writing to them afterward degrades gracefully (see
            # finish_run's None-guard) but won't reach the client anymore.
            for run in s.exec(select(AgentRun).where(AgentRun.status == RunStatus.RUNNING)):
                cancelled_run_ids.append(run.id)
            for table in (PingLog, HosEvent, LiveTrip, LiveLoad, FleetDriver,
                          FleetTruck, FleetException, PendingAction, AgentStep,
                          AgentRun, MessageLog, DocPacket, Invoice, SimState):
                s.exec(delete(table))
            s.commit()
        conn = raw_connection()
        try:
            t0 = datetime.now().replace(minute=0, second=0, microsecond=0)
            build_world(conn, t0)
            build_packets(conn, t0)
        finally:
            conn.close()
        with Session(engine) as s:
            state = s.get(SimState, 1)
            trucks = snapshot_positions(s)
            sim = {
                "sim_now": state.sim_now,
                "speed": state.speed,
                "running": state.running,
                "t0": state.t0,
            }

    # The DB commit/rebuild is authoritative before any client invalidation.
    for run_id in cancelled_run_ids:
        broadcaster.publish("agent_run", {
            "id": run_id,
            "status": "FAILED",
            "summary": "cancelled by demo reset",
            "error": "cancelled by demo reset",
            "finished_at": datetime.now(),
        })
    broadcaster.publish("tick_control", sim)
    broadcaster.publish("positions", {"trucks": trucks})
    broadcaster.publish("world_reset", {"t0": t0})
    return {"ok": True, "t0": t0}
