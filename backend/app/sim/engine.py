"""Background simulation loop: clock -> mover -> HOS -> watchdog -> broadcast."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Awaitable, Callable

from sqlmodel import Session, select

from ..config import SIM_TICK_WALL_SECONDS
from ..db import engine as db_engine
from ..models import FleetException, FleetTruck, LiveTrip, SimState, TripStatus
from ..streams import broadcaster
from . import detectors, mover

log = logging.getLogger("sim")

ExceptionHook = Callable[[int], Awaitable[None]]


class SimEngine:
    def __init__(self) -> None:
        self.on_exception: ExceptionHook | None = None
        self._task: asyncio.Task | None = None
        self._resetting = False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="sim-loop")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

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
                    asyncio.create_task(self.on_exception(exc_id))

    def _tick(self) -> list[int]:
        new_ids: list[int] = []
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

            new_ids = [e.id for e in new_exceptions
                       if e.severity in ("HIGH", "CRITICAL") and e.id is not None]

            broadcaster.publish("tick", {
                "sim_now": state.sim_now,
                "speed": state.speed,
                "running": state.running,
            })
            broadcaster.publish("positions", {"trucks": snapshot_positions(session)})
        return new_ids


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
