"""Dispatch Recommender: deterministic scoring feeds a Gemini tool-loop that
justifies a pick, drafts the driver SMS, and queues it for human approval."""
from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session

from ..db import engine
from ..models import PendingAction
from ..streams import broadcaster
from .gemini import run_agent
from .schemas import DispatchRecommendation
from .tools_common import (
    get_candidate_drivers,
    get_driver,
    get_lane_history,
    get_load,
)

SYSTEM = """You are the dispatch copilot for Sunbelt Carriers, a 14-truck TX/OK
regional fleet. A dispatcher asked you to recommend the best driver for a load.

Method:
1. Pull the load, then the scored candidate list (the score already blends
   deadhead, HOS slack, lane familiarity, on-time history, safety record).
2. Sanity-check the top candidates yourself: verify HOS feasibility against
   the lane length and pickup window; check lane history for detention norms.
3. Recommend ONE driver. Deviate from the top score only with a concrete
   reason (for example a feasibility flag).
4. Write the SMS you would send that driver: plain, friendly, under 320 chars,
   includes lane, pickup window, rate context if useful. No emojis.

Rules: never invent data - every number must come from a tool result. Name the
runner-up and why they lost. List real risks (tight windows, HOS margins,
detention-prone consignee)."""


async def recommend_for_load(load_id: str) -> dict:
    result, run_id = await run_agent(
        kind="dispatch",
        subject_id=load_id,
        system=SYSTEM,
        prompt=f"Find the best driver for load {load_id}. Use the tools, then finalize.",
        tools=[get_load, get_candidate_drivers, get_driver, get_lane_history],
        output_schema=DispatchRecommendation,
    )
    if result is None:
        return {"run_id": run_id, "error": "agent failed"}

    rec: DispatchRecommendation = result
    with Session(engine) as s:
        action = PendingAction(
            run_id=run_id,
            kind="ASSIGN_DRIVER",
            title=f"Assign {rec.recommended_driver_name} to {load_id}",
            subject_id=load_id,
            impact=json.dumps({
                "deadhead_miles": rec.deadhead_miles,
                "risks": rec.risks,
            }),
            draft=json.dumps({
                "driver_id": rec.recommended_driver_id,
                "driver_name": rec.recommended_driver_name,
                "sms_body": rec.sms_draft,
                "alternates": [a.model_dump() for a in rec.alternates],
            }),
            rationale=rec.rationale,
            created_at=datetime.now(),
        )
        s.add(action)
        s.commit()
        s.refresh(action)
    broadcaster.publish("action", {"id": action.id, "kind": action.kind,
                                   "title": action.title, "status": "PENDING"})
    return {"run_id": run_id, "action_id": action.id,
            "recommendation": rec.model_dump()}
