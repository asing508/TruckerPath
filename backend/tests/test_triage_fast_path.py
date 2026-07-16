"""The manual triage fast path: bounded context and one model request."""
from __future__ import annotations

import pytest

from app.agents import triage
from app.agents.schemas import TriageAssessment


def test_triage_context_is_compact_and_conditionally_enriched(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(triage.get_exception, "fn", lambda exception_id: {
        "id": exception_id,
        "type": "HOS_RISK",
        "trip_id": "T-1",
        "driver_id": "D-1",
    })
    monkeypatch.setattr(triage.get_trip_state, "fn", lambda trip_id: {
        "trip_id": trip_id,
        "driver": {
            "driver_id": "D-1",
            "position": {"lat": 32.8, "lon": -96.8},
            "hos": {"drive_min_remaining": 18},
        },
        "load": {
            "route_id": "R-1",
            "customer": {"id": "C-1", "name": "Customer"},
        },
    })

    def recent_pings(trip_id, limit):
        calls["ping_limit"] = limit
        return [{"ts": str(i), "speed_mph": 55} for i in range(limit)]

    def nearby(lat, lon, radius_miles):
        calls["nearby"] = (lat, lon, radius_miles)
        return [{"driver_id": "D-2", "distance_miles": 42}]

    monkeypatch.setattr(triage.get_recent_pings, "fn", recent_pings)
    monkeypatch.setattr(triage.get_lane_history, "fn",
                        lambda route_id: {"route_id": route_id})
    monkeypatch.setattr(triage.get_customer_profile, "fn",
                        lambda customer_id: {"customer_id": customer_id})
    monkeypatch.setattr(triage.find_nearby_drivers, "fn", nearby)

    context = triage.build_triage_context(7)

    assert calls["ping_limit"] == 6
    assert calls["nearby"] == (32.8, -96.8, 250)
    assert len(context["recent_pings"]) == 6
    assert context["driver"]["driver_id"] == "D-1"
    assert context["lane_history"]["route_id"] == "R-1"
    assert context["customer_profile"]["customer_id"] == "C-1"
    assert context["nearby_drivers"][0]["driver_id"] == "D-2"
    assert "detention_math" not in context


@pytest.mark.asyncio
async def test_fast_triage_uses_one_structured_model_call(monkeypatch):
    events: list[tuple[str, str]] = []
    model_calls: list[str] = []
    finished: list[tuple[int, str, str]] = []

    class FakeTracer:
        def emit(self, kind, name="", payload=None):
            events.append((kind, name))

    assessment = TriageAssessment(
        severity="CRITICAL",
        root_cause_hypothesis="Driver is at the HOS limit.",
        recommended_action="PLAN_REST_STOP",
        action_summary="Route to the planned safe stop",
        impact_estimate="No delivery delay expected",
        driver_sms="Proceed to the planned stop and confirm when parked.",
    )

    monkeypatch.setattr(triage.ai_budget, "try_start_run", lambda kind: True)
    monkeypatch.setattr(triage, "GEMINI_TRIAGE_MODEL", "lite-test")
    monkeypatch.setattr(
        triage,
        "start_run",
        lambda kind, subject_id, model=None: (41, FakeTracer()),
    )
    monkeypatch.setattr(
        triage,
        "build_triage_context",
        lambda exception_id: {"exception": {"id": exception_id}},
    )

    async def fake_structured_call(**kwargs):
        model_calls.append(kwargs["model"])
        return assessment

    monkeypatch.setattr(triage, "structured_call", fake_structured_call)
    monkeypatch.setattr(
        triage,
        "finish_run",
        lambda run_id, summary, error="": finished.append(
            (run_id, summary, error),
        ),
    )

    result, run_id = await triage.run_fast_triage(9)

    assert result == assessment
    assert run_id == 41
    assert model_calls == ["lite-test"]
    assert events == [
        ("tool_call", "build_triage_context"),
        ("tool_result", "build_triage_context"),
        ("output", ""),
    ]
    assert finished == [(41, "Route to the planned safe stop", "")]


@pytest.mark.asyncio
async def test_fast_triage_does_no_work_when_budget_denies(monkeypatch):
    monkeypatch.setattr(triage.ai_budget, "try_start_run", lambda kind: False)

    def should_not_run(*args, **kwargs):
        raise AssertionError("context/model work should not start")

    monkeypatch.setattr(triage, "start_run", should_not_run)
    monkeypatch.setattr(triage, "build_triage_context", should_not_run)
    monkeypatch.setattr(triage, "structured_call", should_not_run)

    assert await triage.run_fast_triage(3) == (None, 0)
