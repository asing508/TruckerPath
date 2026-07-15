"""Dispatch board, exceptions, pending actions, agent runs."""
from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session, select

from ..agents import dispatch as dispatch_agent
from ..agents import triage as triage_agent
from ..agents.budget import ai_budget
from ..agents.executor import approve_action, dismiss_action
from ..agents.tools_common import get_candidate_drivers
from ..tasks import spawn
from ..db import engine
from ..models import (
    ActionStatus,
    AgentRun,
    AgentStep,
    ExceptionState,
    FleetDriver,
    FleetException,
    LiveLoad,
    LoadStatus,
    PendingAction,
)

router = APIRouter(prefix="/api", tags=["ops"])


@router.get("/dispatch/board")
def dispatch_board() -> dict:
    with Session(engine) as s:
        unassigned = s.exec(select(LiveLoad)
                            .where(LiveLoad.status == LoadStatus.UNASSIGNED)
                            .order_by(LiveLoad.pickup_window_start)).all()  # type: ignore[arg-type]
        idle = s.exec(select(FleetDriver).where(FleetDriver.trip_id == None)).all()  # noqa: E711
        return {
            "unassigned_loads": [json.loads(l.model_dump_json()) for l in unassigned],
            "idle_drivers": [{
                "driver_id": d.driver_id, "name": d.name, "terminal": d.home_terminal,
                "duty": d.duty,
                "drive_min_remaining": d.drive_min_remaining_calc(),
                "window_min_remaining": d.window_min_remaining_calc(),
                "cycle_min_remaining": d.cycle_min_remaining_calc(),
                "on_time_rate": d.on_time_rate, "incidents": d.incident_count,
            } for d in idle],
        }


@router.get("/dispatch/candidates/{load_id}")
def dispatch_candidates(load_id: str) -> dict:
    return get_candidate_drivers.fn(load_id)


@router.post("/dispatch/recommend/{load_id}")
async def dispatch_recommend(load_id: str) -> dict:
    spawn(dispatch_agent.recommend_for_load(load_id), name=f"dispatch:{load_id}")
    return {"started": True, "load_id": load_id}


@router.get("/exceptions")
def exceptions(include_resolved: bool = False) -> list[dict]:
    with Session(engine) as s:
        q = select(FleetException).order_by(FleetException.updated_at.desc())  # type: ignore[attr-defined]
        rows = s.exec(q.limit(80)).all()
        out = []
        for e in rows:
            if not include_resolved and e.state in (ExceptionState.RESOLVED,
                                                    ExceptionState.DISMISSED):
                continue
            out.append({
                "id": e.id, "type": e.type, "severity": e.severity,
                "state": e.state, "title": e.title,
                "detail": json.loads(e.detail),
                "trip_id": e.trip_id, "driver_id": e.driver_id,
                "truck_id": e.truck_id, "load_id": e.load_id,
                "detected_at": e.detected_at, "updated_at": e.updated_at,
                "agent_run_id": e.agent_run_id,
            })
        return out


@router.post("/exceptions/{exception_id}/triage")
async def manual_triage(exception_id: int) -> dict:
    spawn(triage_agent.triage_exception(exception_id), name=f"triage:{exception_id}")
    return {"started": True}


@router.get("/ai/status")
def ai_status() -> dict:
    return ai_budget.status()


class AutoBody(BaseModel):
    enabled: bool


@router.post("/ai/auto")
def ai_auto(body: AutoBody) -> dict:
    """Toggle watchdog-initiated investigations (the sim never calls the LLM
    while this is off; manual buttons always work within the budget)."""
    return ai_budget.set_auto(body.enabled)


@router.get("/actions")
def actions(status: str = "PENDING") -> list[dict]:
    with Session(engine) as s:
        q = select(PendingAction).order_by(PendingAction.created_at.desc())  # type: ignore[attr-defined]
        rows = s.exec(q.limit(50)).all()
        return [{
            "id": a.id, "run_id": a.run_id, "kind": a.kind, "title": a.title,
            "subject_id": a.subject_id, "impact": json.loads(a.impact),
            "draft": json.loads(a.draft), "rationale": a.rationale,
            "status": a.status, "created_at": a.created_at,
            "decided_at": a.decided_at, "executed_note": a.executed_note,
        } for a in rows if status == "ALL" or a.status == status]


class ApproveBody(BaseModel):
    draft_override: dict | None = None


@router.post("/actions/{action_id}/approve")
def approve(action_id: int, body: ApproveBody | None = None) -> dict:
    return approve_action(action_id, body.draft_override if body else None)


@router.post("/actions/{action_id}/dismiss")
def dismiss(action_id: int) -> dict:
    return dismiss_action(action_id)


@router.get("/agent/runs/{run_id}")
def agent_run(run_id: int) -> dict:
    with Session(engine) as s:
        run = s.get(AgentRun, run_id)
        if run is None:
            return {"error": "not found"}
        steps = s.exec(select(AgentStep).where(AgentStep.run_id == run_id)
                       .order_by(AgentStep.seq)).all()  # type: ignore[arg-type]

        def parse(p: str):
            try:
                return json.loads(p)
            except json.JSONDecodeError:
                return {"raw": p[:2000]}

        return {
            "id": run.id, "kind": run.kind, "subject_id": run.subject_id,
            "status": run.status, "model": run.model, "summary": run.summary,
            "error": run.error, "started_at": run.started_at,
            "finished_at": run.finished_at,
            "steps": [{"seq": st.seq, "kind": st.kind, "name": st.name,
                       "payload": parse(st.payload), "ts": st.ts}
                      for st in steps],
        }


@router.get("/agent/runs")
def agent_runs(limit: int = 20) -> list[dict]:
    with Session(engine) as s:
        rows = s.exec(select(AgentRun).order_by(AgentRun.started_at.desc())  # type: ignore[attr-defined]
                      .limit(limit)).all()
        return [{"id": r.id, "kind": r.kind, "subject_id": r.subject_id,
                 "status": r.status, "model": r.model, "summary": r.summary,
                 "started_at": r.started_at, "finished_at": r.finished_at}
                for r in rows]
