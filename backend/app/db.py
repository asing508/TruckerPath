"""Database engines.

One SQLite file holds both planes:
  - warehouse tables (loaded verbatim from the 14 CSVs + derived stats), queried
    with plain SQL for analytics and by the agent's guarded run_sql tool
  - live-ops tables (SQLModel) written by the simulator and the API
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def raw_connection() -> sqlite3.Connection:
    """Writable connection for bulk ETL work."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# SQLite authorizer action codes that a read-only analyst query may perform.
_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}

# Tables the LLM-generated SQL must never read: audit answer keys and agent
# internals. Enforced at the authorizer level, not just omitted from prompts.
_DENIED_TABLES = {"doc_packets", "agent_runs", "agent_steps", "pending_actions",
                  "message_log", "invoices"}


def readonly_connection() -> sqlite3.Connection:
    """Hardened connection for LLM-generated SQL.

    Defense in depth: the file is opened in SQLite read-only mode AND an
    authorizer denies every action except SELECT/READ (with an explicit table
    denylist), so a crafted ATTACH/PRAGMA/INSERT or a query against the audit
    answer key is rejected at the SQLite VM level.
    """
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")  # before the authorizer locks PRAGMA out

    def authorizer(action: int, arg1, *_: object) -> int:
        if action == sqlite3.SQLITE_READ and arg1 in _DENIED_TABLES:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY

    conn.set_authorizer(authorizer)
    return conn
