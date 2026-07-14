import pytest
from sqlmodel import Session

from app.agents.analyst import run_sql
from app.config import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run seed first")


def test_select_works():
    out = run_sql.fn("SELECT COUNT(*) AS n FROM loads")
    assert out["rows"][0][0] == 85410


def test_row_cap_enforced():
    out = run_sql.fn("SELECT load_id FROM loads")
    assert out["row_count"] <= 120
    assert out["truncated"] is True


def test_writes_rejected():
    out = run_sql.fn("DELETE FROM loads")
    assert "error" in out
    out = run_sql.fn("INSERT INTO loads (load_id) VALUES ('X')")
    assert "error" in out
    out = run_sql.fn("UPDATE loads SET revenue = 0")
    assert "error" in out


def test_ddl_and_pragma_rejected():
    assert "error" in run_sql.fn("DROP TABLE loads")
    assert "error" in run_sql.fn("CREATE TABLE evil (x)")
    assert "error" in run_sql.fn("ATTACH DATABASE 'x.db' AS x")


def test_answer_key_table_denied():
    out = run_sql.fn("SELECT truth FROM doc_packets")
    assert "error" in out
    out = run_sql.fn("SELECT * FROM pending_actions")
    assert "error" in out
