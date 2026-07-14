"""Simulation controls: play / pause / speed / reset."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session, delete

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
    SimState,
)
from ..sim.engine import sim_engine
from ..streams import broadcaster

router = APIRouter(prefix="/api/sim", tags=["sim"])


class SpeedBody(BaseModel):
    speed: int


@router.post("/play")
def play() -> dict:
    with Session(engine) as s:
        state = s.get(SimState, 1)
        state.running = True
        s.add(state)
        s.commit()
    broadcaster.publish("tick_control", {"running": True})
    return {"running": True}


@router.post("/pause")
def pause() -> dict:
    with Session(engine) as s:
        state = s.get(SimState, 1)
        state.running = False
        s.add(state)
        s.commit()
    broadcaster.publish("tick_control", {"running": False})
    return {"running": False}


@router.post("/speed")
def set_speed(body: SpeedBody) -> dict:
    speed = max(1, min(600, body.speed))
    with Session(engine) as s:
        state = s.get(SimState, 1)
        state.speed = speed
        s.add(state)
        s.commit()
    broadcaster.publish("tick_control", {"speed": speed})
    return {"speed": speed}


@router.post("/reset")
def reset() -> dict:
    """Rebuild the live world from the warehouse (route geometry is kept, so
    no network calls). The demo returns to a deterministic T0."""
    sim_engine._resetting = True
    try:
        with Session(engine) as s:
            for table in (PingLog, HosEvent, LiveTrip, LiveLoad, FleetDriver,
                          FleetTruck, FleetException, PendingAction, AgentStep,
                          AgentRun, MessageLog, DocPacket, Invoice, SimState):
                s.exec(delete(table))
            s.commit()
        conn = raw_connection()
        t0 = datetime.now().replace(minute=0, second=0, microsecond=0)
        build_world(conn, t0)
        build_packets(conn, t0)
        conn.close()
        broadcaster.publish("world_reset", {"t0": t0})
        return {"ok": True, "t0": t0}
    finally:
        sim_engine._resetting = False
