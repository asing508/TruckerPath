"""Fleet state, feed, messages, geometry, and SSE stream."""
from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, select

from ..db import engine
from ..models import (
    ActionStatus,
    AgentRun,
    FleetDriver,
    FleetException,
    FleetTruck,
    LiveLoad,
    LiveTrip,
    MessageLog,
    PendingAction,
    RouteGeometry,
    SimState,
    TripStatus,
)
from ..sim.engine import snapshot_positions
from ..streams import broadcaster

router = APIRouter(prefix="/api", tags=["fleet"])


@router.get("/fleet/state")
def fleet_state() -> dict:
    with Session(engine) as s:
        state = s.get(SimState, 1)
        trips = s.exec(select(LiveTrip)).all()
        loads = {l.load_id: l for l in s.exec(select(LiveLoad)).all()}
        drivers = s.exec(select(FleetDriver)).all()
        return {
            "sim": {"sim_now": state.sim_now, "speed": state.speed,
                    "running": state.running, "t0": state.t0},
            "trucks": snapshot_positions(s),
            "drivers": [{
                "driver_id": d.driver_id, "name": d.name, "duty": d.duty,
                "terminal": d.home_terminal, "trip_id": d.trip_id,
                "drive_min_remaining": d.drive_min_remaining_calc(),
                "window_min_remaining": d.window_min_remaining_calc(),
                "cycle_min_remaining": d.cycle_min_remaining_calc(),
                "violations": d.hos_violation_flags,
                "on_time_rate": d.on_time_rate,
            } for d in drivers],
            "trips": [{
                "trip_id": t.trip_id, "load_id": t.load_id, "status": t.status,
                "driver_id": t.driver_id, "truck_id": t.truck_id,
                "progress_miles": round(t.progress_miles, 1),
                "total_miles": t.total_miles,
                "eta_state": t.eta_state,
                "planned_eta": t.planned_eta,
                "projected_eta": t.projected_eta,
                "geometry_id": t.geometry_id,
                "lane": (f"{loads[t.load_id].origin_city} -> {loads[t.load_id].dest_city}"
                         if t.load_id in loads else ""),
                "customer": loads[t.load_id].customer_name if t.load_id in loads else "",
                "detention_min": t.detention_min,
                "last_ping_at": t.last_ping_at,
            } for t in trips if t.status != TripStatus.COMPLETED],
        }


@router.get("/geometry/{geometry_id}")
def geometry(geometry_id: int) -> dict:
    with Session(engine) as s:
        g = s.get(RouteGeometry, geometry_id)
        return {"id": g.id, "lane_key": g.lane_key, "source": g.source,
                "distance_miles": g.distance_miles,
                "points": json.loads(g.encoded_polyline)}


@router.get("/feed")
def feed(limit: int = 40) -> list[dict]:
    """Composite operations feed: exceptions, decided actions, messages, runs."""
    items: list[dict] = []
    with Session(engine) as s:
        for e in s.exec(select(FleetException)
                        .order_by(FleetException.updated_at.desc()).limit(limit)).all():  # type: ignore[attr-defined]
            items.append({"ts": e.updated_at, "kind": "exception",
                          "severity": e.severity, "state": e.state,
                          "text": e.title, "exception_id": e.id, "trip_id": e.trip_id})
        for a in s.exec(select(PendingAction)
                        .order_by(PendingAction.created_at.desc()).limit(limit)).all():  # type: ignore[attr-defined]
            if a.status != ActionStatus.PENDING:
                items.append({"ts": a.decided_at or a.created_at, "kind": "action",
                              "text": f"{a.title} - {a.status}", "action_id": a.id,
                              "status": a.status})
        for m in s.exec(select(MessageLog)
                        .order_by(MessageLog.sent_at.desc()).limit(limit)).all():  # type: ignore[attr-defined]
            items.append({"ts": m.sent_at, "kind": "message", "channel": m.channel,
                          "text": (f"{m.channel} to {m.to_name}: "
                                   f"{m.subject or m.body[:80]}")})
        for r in s.exec(select(AgentRun)
                        .order_by(AgentRun.started_at.desc()).limit(limit)).all():  # type: ignore[attr-defined]
            items.append({"ts": r.started_at, "kind": "agent_run",
                          "text": f"Agent [{r.kind}] {r.status.lower()} - "
                                  f"{r.summary[:120] if r.summary else r.subject_id}",
                          "run_id": r.id, "status": r.status})
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items[:limit]


@router.get("/messages")
def messages(limit: int = 30) -> list[dict]:
    with Session(engine) as s:
        rows = s.exec(select(MessageLog)
                      .order_by(MessageLog.sent_at.desc()).limit(limit)).all()  # type: ignore[attr-defined]
        return [{
            "id": m.id, "channel": m.channel, "to_name": m.to_name,
            "to_addr": m.to_addr, "subject": m.subject, "body": m.body,
            "sent_at": m.sent_at, "trip_id": m.related_trip_id,
            "load_id": m.related_load_id,
        } for m in rows]


@router.get("/stream")
async def stream():
    async def gen():
        with Session(engine) as s:
            state = s.get(SimState, 1)
            yield {"event": "tick", "data": json.dumps({
                "sim_now": state.sim_now.isoformat(), "speed": state.speed,
                "running": state.running})}
            yield {"event": "positions",
                   "data": json.dumps({"trucks": snapshot_positions(s)})}
        async for event, payload in broadcaster.stream():
            yield {"event": event, "data": payload}
    return EventSourceResponse(gen())
