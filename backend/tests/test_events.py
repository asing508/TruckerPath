import asyncio
import json
from datetime import datetime

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.agents import gemini
from app.models import SimState
from app.routers import sim as sim_router
from app.sim import engine as engine_module
from app.streams import Broadcaster


@pytest.mark.asyncio
async def test_worker_thread_publications_wake_subscriber_in_order():
    broadcaster = Broadcaster()

    async with broadcaster.subscribe() as queue:
        def publish_from_worker() -> None:
            broadcaster.publish("first", {"seq": 1})
            broadcaster.publish("second", {"seq": 2})

        await asyncio.to_thread(publish_from_worker)
        first = await asyncio.wait_for(queue.get(), timeout=1)
        second = await asyncio.wait_for(queue.get(), timeout=1)

    assert first[0] == "first"
    assert json.loads(first[1]) == {"seq": 1}
    assert second[0] == "second"
    assert json.loads(second[1]) == {"seq": 2}


def test_agent_events_contain_fields_live_consumers_need(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    SQLModel.metadata.create_all(test_engine)
    published: list[tuple[str, dict]] = []

    monkeypatch.setattr(gemini, "db_engine", test_engine)
    monkeypatch.setattr(gemini, "resolve_model", lambda: "test-model")
    monkeypatch.setattr(
        gemini.broadcaster,
        "publish",
        lambda event, payload: published.append((event, payload)),
    )

    run_id, tracer = gemini.start_run("safety", "D-1")
    tracer.emit("tool_call", name="risk", payload={"driver_id": "D-1"})
    gemini.finish_run(run_id, "brief ready")

    start = published[0]
    assert start[0] == "agent_run"
    assert start[1] == {
        "id": run_id,
        "kind": "safety",
        "subject_id": "D-1",
        "status": "RUNNING",
        "model": "test-model",
        "summary": "",
        "error": "",
        "started_at": start[1]["started_at"],
        "finished_at": None,
    }
    assert isinstance(start[1]["started_at"], datetime)

    step = published[1]
    assert step[0] == "agent_step"
    assert step[1]["run_id"] == run_id
    assert step[1]["seq"] == 1
    assert isinstance(step[1]["ts"], datetime)

    finished = published[2]
    assert finished[0] == "agent_run"
    assert finished[1]["status"] == "DONE"
    assert finished[1]["summary"] == "brief ready"
    assert isinstance(finished[1]["finished_at"], datetime)


def test_pause_publishes_complete_authoritative_sim_state(monkeypatch):
    state = {
        "sim_now": datetime(2026, 7, 14, 12),
        "speed": 30,
        "running": False,
        "t0": datetime(2026, 7, 14, 8),
    }
    published: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        sim_router.sim_engine,
        "update_control",
        lambda **changes: state if changes == {"running": False} else None,
    )
    monkeypatch.setattr(
        sim_router.broadcaster,
        "publish",
        lambda event, payload: published.append((event, payload)),
    )

    assert sim_router.pause() == state
    assert published == [("tick_control", state)]


def test_control_update_commits_and_returns_complete_snapshot(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    SQLModel.metadata.create_all(test_engine)
    t0 = datetime(2026, 7, 14, 8)
    with Session(test_engine) as session:
        session.add(SimState(t0=t0, sim_now=t0, speed=30, running=True))
        session.commit()

    monkeypatch.setattr(engine_module, "db_engine", test_engine)
    local_engine = engine_module.SimEngine()

    state = local_engine.update_control(running=False, speed=999)

    assert state == {
        "sim_now": t0,
        "speed": 600,
        "running": False,
        "t0": t0,
    }
    with Session(test_engine) as session:
        persisted = session.get(SimState, 1)
        assert persisted.running is False
        assert persisted.speed == 600
