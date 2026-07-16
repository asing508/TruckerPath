"""Triage proposals retain real recipients instead of overloading subject_id."""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents import executor, triage
from app.agents.schemas import TriageAssessment
from app.models import (
    DriverDuty,
    ExceptionState,
    ExceptionType,
    FleetDriver,
    FleetException,
    FleetTruck,
    MessageLog,
    PendingAction,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _truck(driver_id: str | None) -> FleetTruck:
    now = datetime(2026, 7, 15, 9)
    return FleetTruck(
        truck_id="TRK-1", unit_number="1001", make="Volvo", model_year=2023,
        home_terminal="Dallas", status="Active", driver_id=driver_id,
        lat=32.8, lon=-96.8, odometer_miles=100_000, last_pm_date=now,
        next_pm_due=now, annual_inspection_expiry=now,
    )


def _exception(now: datetime) -> FleetException:
    return FleetException(
        type=ExceptionType.MAINTENANCE_DUE, severity="HIGH",
        state=ExceptionState.OPEN, truck_id="TRK-1",
        title="Annual inspection due", detail="{}",
        detected_at=now, updated_at=now,
    )


def _assessment() -> TriageAssessment:
    return TriageAssessment(
        severity="HIGH", root_cause_hypothesis="Inspection is due.",
        recommended_action="SCHEDULE_MAINTENANCE",
        action_summary="Schedule the annual inspection",
        impact_estimate="Avoid an out-of-service event",
        driver_sms="Please bring unit 1001 in for its annual inspection.",
    )


async def _create_action(monkeypatch, engine) -> int:
    async def fake_triage(_exception_id):
        return _assessment(), 17

    monkeypatch.setattr(triage, "engine", engine)
    monkeypatch.setattr(triage, "run_fast_triage", fake_triage)
    monkeypatch.setattr(triage.broadcaster, "publish", lambda *args, **kwargs: None)
    with Session(engine) as s:
        exception_id = s.exec(select(FleetException.id)).one()
    return (await triage.triage_exception(exception_id))["action_id"]


@pytest.mark.asyncio
async def test_no_trip_sms_uses_driver_assigned_to_exception_truck(monkeypatch):
    engine = _engine()
    now = datetime(2026, 7, 15, 9)
    driver = FleetDriver(
        driver_id="DRV-1", name="Avery Driver", phone="+15550000001",
        home_terminal="Dallas", years_experience=5, duty=DriverDuty.OFF,
        lat=32.8, lon=-96.8, on_time_rate=0.95, avg_mpg=7.1,
        incident_count=0, revenue_per_mile=2.4,
    )
    with Session(engine) as s:
        s.add_all([driver, _truck("DRV-1"), _exception(now)])
        s.commit()

    action_id = await _create_action(monkeypatch, engine)

    with Session(engine) as s:
        action = s.get(PendingAction, action_id)
        impact, draft = json.loads(action.impact), json.loads(action.draft)
        assert action.kind == "SMS_DRIVER"
        assert action.subject_id == "TRK-1"
        assert impact["driver_id"] == "DRV-1"
        assert impact["trip_id"] is None
        assert draft["driver_name"] == "Avery Driver"

        note = executor._comms(s, action, draft, now, [])
        s.commit()
        message = s.exec(select(MessageLog)).one()
        assert note == "SMS to Avery Driver"
        assert message.to_name == "Avery Driver"
        assert message.related_trip_id is None


@pytest.mark.asyncio
async def test_sms_is_not_offered_when_exception_has_no_driver(monkeypatch):
    engine = _engine()
    now = datetime(2026, 7, 15, 9)
    with Session(engine) as s:
        s.add_all([_truck(None), _exception(now)])
        s.commit()

    action_id = await _create_action(monkeypatch, engine)

    with Session(engine) as s:
        action = s.get(PendingAction, action_id)
        assert action.kind == "MONITOR"
        assert "sms_body" not in json.loads(action.draft)
        assert json.loads(action.impact)["driver_id"] is None
