"""Fleet Copilot backend.

Boot order: ensure the database exists (auto-seed on first run), resolve the
Gemini model, start the simulation loop, and wire the watchdog to the triage
agent so HIGH/CRITICAL exceptions get investigated automatically.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agents.gemini import resolve_model
from .agents.triage import triage_exception
from .config import DB_PATH, FRONTEND_ORIGIN
from .db import init_db
from .routers import analytics, billing, fleet, ops, safety, sim
from .sim.engine import sim_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


def _sweep_orphaned_runs() -> None:
    """Agent runs die with the process; on boot, fail leftovers and reopen
    their exceptions so triage can run again."""
    from sqlmodel import Session, select

    from .db import engine
    from .models import AgentRun, ExceptionState, FleetException, RunStatus

    with Session(engine) as s:
        stale = s.exec(select(AgentRun).where(AgentRun.status == RunStatus.RUNNING)).all()
        for run in stale:
            run.status = RunStatus.FAILED
            run.error = "orphaned by server restart"
            s.add(run)
        stuck = s.exec(select(FleetException).where(
            FleetException.state == ExceptionState.TRIAGING)).all()
        for exc in stuck:
            exc.state = ExceptionState.OPEN
            s.add(exc)
        from .models import DocPacket, PacketStatus
        hung = s.exec(select(DocPacket).where(
            DocPacket.status == PacketStatus.AUDITING)).all()
        for p in hung:
            p.status = PacketStatus.READY
            s.add(p)
        if stale or stuck or hung:
            log.info("swept %d orphaned runs, %d stuck exceptions, %d hung audits",
                     len(stale), len(stuck), len(hung))
        s.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DB_PATH.exists():
        log.info("no database found - running full seed (first boot)")
        from .etl.seed import main as run_seed
        run_seed()
    init_db()
    _sweep_orphaned_runs()
    model = resolve_model()
    log.info("gemini model resolved: %s", model)

    # Auto-triage with a cooldown: at most 3 automatic runs per 10 wall-minutes,
    # so background triage never starves interactive agents of LLM quota.
    triage_times: list[float] = []

    async def on_exception(exception_id: int) -> None:
        import time
        now = time.monotonic()
        triage_times[:] = [t for t in triage_times if now - t < 600]
        if len(triage_times) >= 3:
            log.info("auto-triage cooldown active; exception %d left in queue",
                     exception_id)
            return
        triage_times.append(now)
        await triage_exception(exception_id)

    sim_engine.on_exception = on_exception
    sim_engine.start()
    log.info("simulation loop started")
    yield
    await sim_engine.stop()


app = FastAPI(title="Fleet Copilot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fleet.router)
app.include_router(sim.router)
app.include_router(ops.router)
app.include_router(analytics.router)
app.include_router(safety.router)
app.include_router(billing.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": resolve_model()}
