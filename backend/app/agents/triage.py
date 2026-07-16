"""Fast exception triage over one request-scoped evidence bundle.

The watchdog detects the issue for free. On a manual click (or a gated
CRITICAL escalation), Python gathers the small set of relevant fleet facts and
Gemini produces one structured assessment in a single logical request.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from google.genai import types
from sqlmodel import Session

from ..config import GEMINI_TRIAGE_MODEL
from ..db import engine
from ..models import (
    ExceptionState,
    FleetDriver,
    FleetException,
    FleetTruck,
    LiveLoad,
    LiveTrip,
    PendingAction,
)
from ..streams import broadcaster
from .budget import ai_budget
from .gemini import finish_run, resolve_model, start_run, structured_call
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

log = logging.getLogger("agents.triage")

SYSTEM = """You are the operations copilot for Sunbelt Carriers (14-truck TX/OK
fleet). The monitoring system opened an exception on a live load. The backend
has already assembled verified, read-only fleet context. Use that context to
propose exactly one next action for the dispatcher to approve.

Method:
1. Start with detector evidence and current trip/driver state.
2. Corroborate with recent pings, lane history, customer history, nearby
   drivers, or detention math when those sections are present.
3. Decide the single best action. Prefer the least disruptive option that
   protects the delivery promise. RELAY_SWAP only when HOS math truly fails.
4. If customers should be told, draft the email: subject + body, professional,
   specific times, no blame, offers a concrete new commitment.
5. If the driver should act, draft the SMS: under 300 chars, plain language.

Rules: cite only tool evidence. State impact in dollars or minutes when the
data supports it. Do not invent weather, traffic, or breakdown causes - if the
telemetry cannot distinguish causes, say what the possibilities are and pick
the action robust to them. Only draft a driver SMS or customer email when the
verified context contains that recipient."""

_semaphore = asyncio.Semaphore(1)


def _action_targets(s: Session, exc: FleetException) -> dict:
    """Resolve durable action recipients from explicit fleet relationships."""
    trip = s.get(LiveTrip, exc.trip_id) if exc.trip_id else None
    truck_id = exc.truck_id or (trip.truck_id if trip else None)
    truck = s.get(FleetTruck, truck_id) if truck_id else None
    driver_id = exc.driver_id or (trip.driver_id if trip else None)
    if not driver_id and truck:
        driver_id = truck.driver_id
    driver = s.get(FleetDriver, driver_id) if driver_id else None

    load_id = exc.load_id or (trip.load_id if trip else None)
    load = s.get(LiveLoad, load_id) if load_id else None
    return {
        "trip_id": trip.trip_id if trip else None,
        "driver_id": driver.driver_id if driver else None,
        "driver_name": driver.name if driver else None,
        "truck_id": truck.truck_id if truck else truck_id,
        "load_id": load.load_id if load else None,
        "customer_name": load.customer_name if load else None,
    }


def build_triage_context(exception_id: int) -> dict:
    """Collect a compact, request-scoped evidence bundle.

    Nothing is cached or retained in memory after the run. Pings and nearby
    alternatives are capped, and expensive sections are included only when
    relevant to the exception type.
    """
    exception = get_exception.fn(exception_id)
    context: dict = {
        "context_version": 1,
        "exception": exception,
    }
    if "error" in exception:
        return context

    trip_id = exception.get("trip_id")
    driver_id = exception.get("driver_id")
    trip: dict = {}

    if trip_id:
        trip = get_trip_state.fn(trip_id)
        context["trip"] = trip
        context["recent_pings"] = get_recent_pings.fn(trip_id, limit=6)

    trip_driver = trip.get("driver") if isinstance(trip, dict) else None
    if isinstance(trip_driver, dict) and "error" not in trip_driver:
        context["driver"] = trip_driver
    elif driver_id:
        context["driver"] = get_driver.fn(driver_id)

    load = trip.get("load", {}) if isinstance(trip, dict) else {}
    if isinstance(load, dict):
        route_id = load.get("route_id")
        customer = load.get("customer") or {}
        customer_id = customer.get("id") if isinstance(customer, dict) else None
        if route_id:
            context["lane_history"] = get_lane_history.fn(route_id)
        if customer_id:
            context["customer_profile"] = get_customer_profile.fn(customer_id)

    exception_type = str(exception.get("type", ""))
    if exception.get("truck_id") and "driver" not in context:
        with Session(engine) as s:
            exc = s.get(FleetException, exception_id)
            targets = _action_targets(s, exc) if exc else {}
        context["recipients"] = {
            "driver_id": targets.get("driver_id"),
            "driver_name": targets.get("driver_name"),
            "customer_name": targets.get("customer_name"),
        }
        if targets.get("driver_id"):
            context["driver"] = get_driver.fn(targets["driver_id"])
    if exception_type == "HOS_RISK":
        driver = context.get("driver") or {}
        position = driver.get("position") if isinstance(driver, dict) else None
        if (
            isinstance(position, dict)
            and position.get("lat") is not None
            and position.get("lon") is not None
        ):
            context["nearby_drivers"] = find_nearby_drivers.fn(
                position["lat"], position["lon"], radius_miles=250,
            )

    if exception_type == "DETENTION" and trip_id:
        context["detention_math"] = get_detention_math.fn(trip_id)

    return context


async def run_fast_triage(
    exception_id: int,
) -> tuple[TriageAssessment | None, int]:
    """Build context once and make one structured Gemini request.

    There is intentionally no timeout and no in-memory cache.
    """
    if not ai_budget.try_start_run("triage"):
        return None, 0

    model = GEMINI_TRIAGE_MODEL or resolve_model()
    run_id, tracer = start_run("triage", str(exception_id), model=model)
    try:
        tracer.emit(
            "tool_call",
            name="build_triage_context",
            payload={"exception_id": exception_id, "invoked_by": "backend_fast_path"},
        )
        context = await asyncio.to_thread(build_triage_context, exception_id)
        tracer.emit("tool_result", name="build_triage_context", payload=context)

        compact_context = json.dumps(context, default=str, separators=(",", ":"))
        result = await structured_call(
            system=SYSTEM,
            parts=[types.Part.from_text(
                text=(
                    f"Exception #{exception_id} just fired. Analyze this verified "
                    f"fleet context and finalize one action:\n{compact_context}"
                ),
            )],
            output_schema=TriageAssessment,
            model=model,
            temperature=0.2,
        )
        assessment = TriageAssessment.model_validate(result)
        tracer.emit("output", payload=assessment.model_dump())
        finish_run(run_id, summary=assessment.action_summary)
        return assessment, run_id
    except Exception as exc:
        log.exception("fast triage run %s failed", run_id)
        tracer.emit("error", payload={"error": str(exc)[:800]})
        finish_run(run_id, summary="", error=str(exc))
        return None, run_id


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

        result, run_id = await run_fast_triage(exception_id)

        with Session(engine) as s:
            exc = s.get(FleetException, exception_id)
            if result is None:
                exc.state = ExceptionState.OPEN  # let a human retry
                s.add(exc)
                s.commit()
                broadcaster.publish("exception", {
                    "id": exception_id,
                    "state": "OPEN",
                })
                return {"run_id": run_id, "error": "agent failed"}

            assessment: TriageAssessment = result
            exc.state = ExceptionState.TRIAGED
            exc.agent_run_id = run_id
            s.add(exc)

            targets = _action_targets(s, exc)
            draft: dict = {"action": assessment.recommended_action,
                           "summary": assessment.action_summary}
            if assessment.customer_email and targets["load_id"]:
                draft["email_subject"] = assessment.customer_email.subject
                draft["email_body"] = assessment.customer_email.body
            if assessment.driver_sms and targets["driver_id"]:
                draft["sms_body"] = assessment.driver_sms
                draft["driver_name"] = targets["driver_name"]

            if assessment.recommended_action == "MONITOR":
                kind = "MONITOR"
            elif draft.get("sms_body"):
                kind = "SMS_DRIVER"
            elif draft.get("email_body"):
                kind = "EMAIL_CUSTOMER"
            else:
                # Do not offer a communication action that cannot be delivered.
                kind = "MONITOR"

            action = PendingAction(
                run_id=run_id,
                kind=kind,
                title=f"[{assessment.severity}] {assessment.action_summary[:110]}",
                subject_id=(targets["trip_id"] or targets["load_id"]
                            or targets["truck_id"] or str(exception_id)),
                impact=json.dumps({"estimate": assessment.impact_estimate,
                                   "exception_id": exception_id,
                                   "trip_id": targets["trip_id"],
                                   "driver_id": targets["driver_id"],
                                   "truck_id": targets["truck_id"],
                                   "load_id": targets["load_id"]}),
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
