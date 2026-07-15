"""The AI event gate: request metering, persistence, rollover, admission
control, the model circuit breaker, and billing extraction resume."""
import json

import pytest
from sqlmodel import SQLModel, create_engine

from app.agents import billing, budget, gemini
from app.agents.budget import AiBudget


@pytest.fixture()
def gate_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'gate.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(budget, "db_engine", engine)
    monkeypatch.setattr(budget.broadcaster, "publish", lambda *a, **k: None)
    return engine


def test_budget_meters_requests_and_survives_restart(gate_db):
    b = AiBudget(request_cap=3, run_reserve=1)
    assert [b.spend_request() for _ in range(4)] == [True, True, True, False]
    assert b.status()["remaining"] == 0

    # a "restarted server" (fresh instance, same DB) sees the same spend
    b2 = AiBudget(request_cap=3, run_reserve=1)
    assert b2.status()["used"] == 3
    assert b2.spend_request() is False


def test_budget_resets_on_quota_day_rollover(gate_db, monkeypatch):
    b = AiBudget(request_cap=2, run_reserve=1)
    monkeypatch.setattr(budget, "quota_day", lambda: "2026-07-14")
    assert b.spend_request() and b.spend_request()
    assert b.spend_request() is False

    monkeypatch.setattr(budget, "quota_day", lambda: "2026-07-15")
    assert b.status()["used"] == 0
    assert b.spend_request() is True

    # yesterday's row is untouched history
    monkeypatch.setattr(budget, "quota_day", lambda: "2026-07-14")
    assert b.status()["used"] == 2


def test_run_reserve_refuses_admission_before_midflight_death(gate_db):
    b = AiBudget(request_cap=10, run_reserve=4)
    assert b.try_start_run("triage") is True
    for _ in range(7):
        b.spend_request()
    # 3 requests left < reserve of 4: refuse the run, requests stay unspent
    assert b.try_start_run("triage") is False
    assert b.status()["used"] == 7


def test_auto_gate_requires_toggle_and_hourly_gap(gate_db):
    b = AiBudget(request_cap=100, run_reserve=5, auto_enabled=False,
                 auto_min_gap_s=3600)
    assert b.allow_auto() is False          # default off
    b.set_auto(True)
    assert b.allow_auto() is True
    assert b.allow_auto() is False          # inside the hourly gap


@pytest.mark.asyncio
async def test_circuit_breaker_benches_exhausted_model(monkeypatch):
    monkeypatch.setattr(gemini, "_cooldown_until", {})
    monkeypatch.setattr(gemini, "MODEL_PREFERENCE",
                        ["model-a", "model-b", "model-c"])
    calls: list[str] = []

    async def fake_call(m, **kwargs):
        calls.append(m)
        if m == "model-a":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return f"ok:{m}"

    monkeypatch.setattr(gemini, "_call_model", fake_call)

    assert await gemini._generate("model-a") == "ok:model-b"
    assert gemini._cooldown_until["model-a"] > 0

    # while benched, model-a is not probed again
    calls.clear()
    assert await gemini._generate("model-a") == "ok:model-b"
    assert calls == ["model-b"]


@pytest.mark.asyncio
async def test_one_logical_request_touches_at_most_two_buckets(monkeypatch):
    monkeypatch.setattr(gemini, "_cooldown_until", {})
    monkeypatch.setattr(gemini, "MODEL_PREFERENCE",
                        ["model-a", "model-b", "model-c", "model-d"])
    calls: list[str] = []

    async def all_exhausted(m, **kwargs):
        calls.append(m)
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(gemini, "_call_model", all_exhausted)

    with pytest.raises(RuntimeError):
        await gemini._generate("model-a")
    assert calls == ["model-a", "model-b"]  # c and d never touched


def test_billing_resume_skips_already_extracted_docs():
    docs = [{"doc_type": "RATE_CONFIRMATION", "filename": "rc.pdf"},
            {"doc_type": "BOL", "filename": "bol.pdf"},
            {"doc_type": "FUEL_RECEIPT", "filename": "fuel1.pdf"}]

    # fresh packet: nothing done
    extraction, done = billing.resume_state(docs, "{}")
    assert done == set() and extraction == {"FUEL_RECEIPTS": []}

    # died after two docs: exactly those two are skipped on retry
    partial = json.dumps({"RATE_CONFIRMATION": {"rate": 1200},
                          "FUEL_RECEIPTS": [],
                          "_done": ["bol.pdf", "rc.pdf"]})
    extraction, done = billing.resume_state(docs, partial)
    assert done == {"rc.pdf", "bol.pdf"}
    assert extraction["RATE_CONFIRMATION"] == {"rate": 1200}

    # legacy pre-"_done" extraction came from a full success: all docs done
    legacy = json.dumps({"RATE_CONFIRMATION": {}, "BOL": {},
                         "FUEL_RECEIPTS": [{}]})
    _, done = billing.resume_state(docs, legacy)
    assert done == {"rc.pdf", "bol.pdf", "fuel1.pdf"}
