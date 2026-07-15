"""Background simulation loop: clock -> mover -> HOS -> watchdog -> broadcast."""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import contextmanager
from datetime import timedelta
from typing import Awaitable, Callable, Iterator

from sqlmodel import Session, select

from ..config import SIM_TICK_WALL_SECONDS
from ..db import engine as db_engine
from ..models import (
    ExceptionType,
    FleetException,
    FleetTruck,
    LiveTrip,
    SimState,
    TripStatus,
)
from ..streams import broadcaster
from ..tasks import spawn
from . import detectors, mover

log = logging.getLogger("sim")

ExceptionHook = Callable[[int], Awaitable[None]]


class SimEngine:
    def __init__(self) -> None:
        self.on_exception: ExceptionHook | None = None
        self._task: asyncio.Task | None = None
        self._resetting = False
        # Simulation ticks run on the event-loop thread while sync FastAPI
        # control routes run in AnyIO worker threads. Serialize their DB
        # mutations so pause/speed/reset cannot race a tick.
        self._state_lock = threading.RLock()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="sim-loop")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def update_control(
        self, *, running: bool | None = None, speed: int | None = None
    ) -> dict:
        """Atomically update controls and return a complete SSE snapshot."""
        with self._state_lock, Session(db_engine) as session:
            state = session.get(SimState, 1)
            if state is None:
                raise RuntimeError("simulation state is not initialized")
            if running is not None:
                state.running = running
            if speed is not None:
                state.speed = max(1, min(600, speed))
            session.add(state)
            session.commit()
            session.refresh(state)
            return snapshot_sim_state(state)

    @contextmanager
    def mutation_guard(self) -> Iterator[None]:
        """Serialize any API mutation that touches the live simulation."""
        with self._state_lock:
            yield

    @contextmanager
    def exclusive_reset(self) -> Iterator[None]:
        """Exclude ticks and control writes while the live world is rebuilt."""
        with self.mutation_guard():
            self._resetting = True
            try:
                yield
            finally:
                self._resetting = False

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(SIM_TICK_WALL_SECONDS)
            if self._resetting:
                continue
            try:
                new_exception_ids = self._tick()
            except Exception:  # keep the loop alive; surface in logs
                log.exception("sim tick failed")
                continue
            if self.on_exception:
                for exc_id in new_exception_ids:
                    spawn(self.on_exception(exc_id), name=f"auto-triage:{exc_id}")

    def _tick(self) -> list[int]:
        # Reset can take longer than a tick. Do not block the event loop behind
        # a worker-thread reset; skip this cadence and try again in two seconds.
        if not self._state_lock.acquire(blocking=False):
            return []
        new_ids: list[int] = []
        try:
            with Session(db_engine) as session:
                state = session.get(SimState, 1)
                if state is None or not state.running:
                    return []
                state.sim_now = state.sim_now + timedelta(
                    seconds=SIM_TICK_WALL_SECONDS * state.speed)
                session.add(state)

                mover.tick(session, state.sim_now, timedelta(
                    seconds=SIM_TICK_WALL_SECONDS * state.speed))
                detectors.refresh_hos_snapshots(session, state.sim_now)
                new_exceptions = detectors.tick(session, state.sim_now)
                session.commit()

                # Auto-triage only time-critical in-transit incidents; maintenance
                # sits in the queue for manual triage (and spares LLM quota).
                new_ids = [e.id for e in new_exceptions
                           if e.severity in ("HIGH", "CRITICAL") and e.id is not None
                           and e.type != ExceptionType.MAINTENANCE_DUE]

                broadcaster.publish("tick", snapshot_sim_state(state))
                broadcaster.publish("positions", {"trucks": snapshot_positions(session)})
            return new_ids
        finally:
            self._state_lock.release()


def snapshot_sim_state(state: SimState) -> dict:
    return {
        "sim_now": state.sim_now,
        "speed": state.speed,
        "running": state.running,
        "t0": state.t0,
    }


def snapshot_positions(session: Session) -> list[dict]:
    out = []
    trips = {t.trip_id: t for t in session.exec(
        select(LiveTrip).where(LiveTrip.status.not_in([TripStatus.COMPLETED]))  # type: ignore[attr-defined]
    ).all()}
    for truck in session.exec(select(FleetTruck)).all():
        trip = trips.get(truck.trip_id) if truck.trip_id else None
        out.append({
            "truck_id": truck.truck_id,
            "unit": truck.unit_number,
            "lat": round(truck.lat, 5),
            "lon": round(truck.lon, 5),
            "heading": round(truck.heading_deg, 0),
            "speed_mph": truck.speed_mph,
            "status": truck.status,
            "trip_id": truck.trip_id,
            "trip_status": trip.status if trip else None,
            "eta_state": trip.eta_state if trip else None,
            "fuel_pct": round(truck.fuel_pct, 0),
        })
    return out


sim_engine = SimEngine()
