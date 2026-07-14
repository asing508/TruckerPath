"""Drives the seeded world forward synchronously and asserts the scripted
faults are detected by the watchdog (not injected as alerts)."""
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.config import DB_PATH
from app.db import engine
from app.models import ExceptionType, FleetException, SimState
from app.sim import detectors, mover

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run seed first")


def test_faults_get_detected_within_two_sim_hours():
    with Session(engine) as session:
        state = session.get(SimState, 1)
        now = state.sim_now
        step = timedelta(minutes=5)
        for _ in range(24):  # 2 simulated hours
            now += step
            mover.tick(session, now, step)
            detectors.refresh_hos_snapshots(session, now)
            detectors.tick(session, now)
            session.flush()

        types = {e.type for e in session.exec(select(FleetException)).all()}
        session.rollback()

    assert ExceptionType.DETENTION in types      # dwell script at the pickup dock
    assert ExceptionType.MAINTENANCE_DUE in types  # overdue PM truck
    assert ExceptionType.ETA_RISK in types or ExceptionType.DARK_LOAD in types
