from pathlib import Path

import psycopg
import pytest

SCRIPT = Path(__file__).parent / "sql" / "schema_test.sql"


def script_sql(keep_transaction=True):
    # Bỏ lệnh psql (\echo ...) để chạy qua psycopg; script tự BEGIN/ROLLBACK
    lines = [line for line in SCRIPT.read_text().splitlines() if not line.lstrip().startswith("\\")]
    if not keep_transaction:
        lines = [line for line in lines if line.strip() not in ("BEGIN;", "ROLLBACK;")]
    return "\n".join(lines)


def test_schema_test_script_passes(db):
    db.execute(script_sql())
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0  # không để lại dữ liệu


def test_schema_test_catches_a_dropped_constraint(db):
    db.execute("BEGIN")
    try:
        db.execute("ALTER TABLE students DROP CONSTRAINT students_grade_check")
        with pytest.raises(psycopg.Error, match="SHOULD HAVE FAILED"):
            db.execute(script_sql(keep_transaction=False))
    finally:
        db.execute("ROLLBACK")
