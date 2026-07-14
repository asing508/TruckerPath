"""Exception Triage: when the watchdog opens a HIGH/CRITICAL exception the
agent investigates with tools and proposes one concrete action for approval."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlmodel import Session

from ..db import engine
from ..models import ExceptionState, FleetException, PendingAction
from ..streams import broadcaster
from .gemini import run_agent
from .schemas import TriageAssessment
from .tools_common import (
    find_nearby_drivers,
    get_customer_profile,
    get_detention_math,
    get_driver,
    get_exception,
    get_lane_history,
    get_recent_pings,
    get_trip_state,
)

SYSTEM = """You are the operations copilot for Sunbelt Carriers (14-truck TX/OK
fleet). The monitoring system opened an exception on a live load. Investigate
and propose exactly one next action for the dispatcher to approve.

Method:
1. get_exception for detector evidence, then get_trip_state.
2. Corroborate: recent pings for movement, driver HOS if relevant, lane
   history for whether this lane is chronically late, customer profile when
   customer communication may be needed.
3. Decide the single best action. Prefer the least disruptive action that
   protects the delivery promise. RELAY_SWAP only when HOS math truly fails.
4. If customers should be told, draft the email: subject + body, professional,
   specific times, no blame, offers a concrete new commitment.
5. If the driver should act, draft the SMS: under 300 chars, plain language.

Rules: cite only tool evidence. State impact in dollars or minutes when the
data supports it. Do not invent weather, traffic, or breakdown causes - if the
telemetry cannot distinguish causes, say what the possibilities are and pick
the action robust to them."""

_semaphore = asyncio.Semaphore(1)  # serialize auto-triage: free-tier quotas are tight


async def triage_exception(exception_id: int) -> dict:
    async with _semaphore:
        with Session(engine) as s:
            exc = s.get(FleetException, exception_id)
            if exc is None or exc.state not in (ExceptionState.OPEN,):
                return {"skipped": True}
            exc.state = ExceptionState.TRIAGING
            s.add(exc)
            s.commit()
        broadcaster.publish("exception", {"id": exception_id, "state": "TRIAGING"})

        result, run_id = await run_agent(
            kind="triage",
            subject_id=str(exception_id),
            system=SYSTEM,
            prompt=f"Exception #{exception_id} just fired. Investigate and finalize.",
            tools=[get_exception, get_trip_state, get_recent_pings, get_driver,
                   find_nearby_drivers, get_lane_history, get_customer_profile,
                   get_detention_math],
            output_schema=TriageAssessment,
        )

        with Session(engine) as s:
            exc = s.get(FleetException, exception_id)
            if result is None:
                exc.state = ExceptionState.OPEN  # let a human retry
                s.add(exc)
                s.commit()
                return {"run_id": run_id, "error": "agent failed"}

            assessment: TriageAssessment = result
            exc.state = ExceptionState.TRIAGED
            exc.agent_run_id = run_id
            s.add(exc)

            draft: dict = {"action": assessment.recommended_action,
                           "summary": assessment.action_summary}
            kind = "SMS_DRIVER" if assessment.driver_sms else "EMAIL_CUSTOMER"
            if assessment.recommended_action == "MONITOR":
                kind = "MONITOR"
            if assessment.customer_email:
                draft["email_subject"] = assessment.customer_email.subject
                draft["email_body"] = assessment.customer_email.body
            if assessment.driver_sms:
                draft["sms_body"] = assessment.driver_sms

            action = PendingAction(
                run_id=run_id,
                kind=kind,
                title=f"[{assessment.severity}] {assessment.action_summary[:110]}",
                subject_id=exc.trip_id or str(exception_id),
                impact=json.dumps({"estimate": assessment.impact_estimate,
                                   "exception_id": exception_id}),
                draft=json.dumps(draft),
                rationale=f"{assessment.root_cause_hypothesis}",
                created_at=datetime.now(),
            )
            s.add(action)
            s.commit()
            s.refresh(action)

        broadcaster.publish("exception", {"id": exception_id, "state": "TRIAGED"})
        broadcaster.publish("action", {"id": action.id, "kind": action.kind,
                                       "title": action.title, "status": "PENDING"})
        return {"run_id": run_id, "action_id": action.id,
                "assessment": result.model_dump()}
