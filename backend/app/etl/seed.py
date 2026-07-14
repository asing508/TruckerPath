"""Seed everything: warehouse, live world, billing packets.

Run:  uv run python -m app.etl.seed
"""
from __future__ import annotations

import shutil
from datetime import datetime

from ..config import DATA_DIR, DB_PATH, DOCS_DIR, INVOICE_DIR
from ..db import init_db, raw_connection
from .docgen import build_packets
from .warehouse import build_warehouse
from .world import build_world

EXPECTED = {
    "drivers": 150, "trucks": 120, "trailers": 180, "customers": 200,
    "facilities": 50, "routes": 58, "loads": 85410, "trips": 85410,
    "fuel_purchases": 196442, "maintenance_records": 2920,
    "delivery_events": 170820, "safety_incidents": 170,
    "driver_monthly_metrics": 4464, "truck_utilization_metrics": 3312,
}


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    if INVOICE_DIR.exists():
        shutil.rmtree(INVOICE_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] warehouse: loading 14 CSVs ...")
    conn = raw_connection()
    counts = build_warehouse(conn)
    for table, n in counts.items():
        flag = "" if EXPECTED.get(table) == n else f"  (expected {EXPECTED.get(table)})"
        print(f"       {table:<28} {n:>7,}{flag}")
    bad = {t: n for t, n in counts.items() if EXPECTED.get(t) != n}
    if bad:
        raise SystemExit(f"row-count mismatch: {bad}")

    print("[2/4] live plane: creating ORM tables ...")
    init_db()

    t0 = datetime.now().replace(minute=0, second=0, microsecond=0)
    print(f"[3/4] live world @ T0={t0:%Y-%m-%d %H:%M} ...")
    world = build_world(conn, t0)
    for k, v in world.items():
        print(f"       {k:<20} {v}")

    print("[4/4] billing packets ...")
    packets = build_packets(conn, t0)
    print(f"       {packets}")
    conn.close()
    print("done. db:", DB_PATH)


if __name__ == "__main__":
    main()
