import shutil
import threading
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from app.migrate import MIGRATIONS_DIR, MigrationError, migrate
from tests.conftest import _admin_url


@pytest.fixture
def scratch_url(test_database):
    url = urlunsplit(urlsplit(test_database)._replace(path="/lusia_scratch_test"))
    with psycopg.connect(_admin_url(url), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS lusia_scratch_test WITH (FORCE)")
        conn.execute("CREATE DATABASE lusia_scratch_test")
    yield url
    with psycopg.connect(_admin_url(url), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS lusia_scratch_test WITH (FORCE)")


def recorded(url):
    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY 1")]


ALL = ["000_init", "001_student_language_agent_name", "002_embedding_1024", "003_document_processing", "004_document_publishing", "005_traces"]


def test_fresh_database_applies_and_records_every_file(scratch_url):
    assert migrate(scratch_url) == ALL
    assert recorded(scratch_url) == ALL


def test_rerun_is_a_noop(scratch_url):
    migrate(scratch_url)
    assert migrate(scratch_url) == []


def test_failing_migration_is_atomic_and_stops(scratch_url, tmp_path):
    for f in MIGRATIONS_DIR.glob("*.sql"):
        shutil.copy(f, tmp_path)
    (tmp_path / "900_bad.sql").write_text("CREATE TABLE half_done (id int);\nSELECT * FROM no_such_table;")
    (tmp_path / "901_after.sql").write_text("CREATE TABLE after_bad (id int);")
    with pytest.raises(MigrationError, match="900_bad.sql"):
        migrate(scratch_url, directory=tmp_path)
    assert recorded(scratch_url) == ALL
    with psycopg.connect(scratch_url) as conn:
        assert conn.execute("SELECT to_regclass('half_done'), to_regclass('after_bad')").fetchone() == (None, None)


def test_concurrent_runners_apply_each_file_once(scratch_url):
    results, errors = [], []

    def run():
        try:
            results.append(migrate(scratch_url))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sorted(results, key=len) == [[], ALL]
    assert recorded(scratch_url) == ALL


def test_baseline_adopts_schema_sql_database(scratch_url):
    with psycopg.connect(scratch_url, autocommit=True) as conn:  # DB tạo trực tiếp từ schema.sql cũ
        conn.execute((MIGRATIONS_DIR / "000_init.sql").read_text())
    assert migrate(scratch_url, baseline=["000_init"]) == ["000_init"]
    assert migrate(scratch_url) == ALL[1:]


def test_baseline_rejects_unknown_name(scratch_url):
    with pytest.raises(MigrationError, match="999_nope"):
        migrate(scratch_url, baseline=["999_nope"])


def add_student(db, language=None):
    uid = db.execute("INSERT INTO users (full_name, username, password_hash) VALUES ('Em A', 'ema', '!no-credential')"
                     " RETURNING id").fetchone()[0]
    if language is None:
        db.execute("INSERT INTO students (user_id, grade) VALUES (%s, 8)", (uid,))
    else:
        db.execute("INSERT INTO students (user_id, grade, language) VALUES (%s, 8, %s)", (uid, language))
    return uid


def test_default_language_is_vi(db):
    uid = add_student(db)
    assert db.execute("SELECT language FROM students WHERE user_id = %s", (uid,)).fetchone()[0] == "vi"


def test_unsupported_language_rejected(db):
    uid = add_student(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE students SET language = 'en' WHERE user_id = %s", (uid,))


def test_student_model_agent_message_accepted(db):
    uid = add_student(db)
    sid = db.execute("INSERT INTO learning_sessions (student_id) VALUES (%s) RETURNING id", (uid,)).fetchone()[0]
    db.execute("INSERT INTO messages (session_id, role, agent, content) VALUES (%s, 'assistant', 'student_model', 'x')",
               (sid,))


def add_document(db, status="processing", error=None):
    return db.execute("INSERT INTO documents (kind, title, subject, grade, storage_key, status, error)"
                      " VALUES ('textbook', 'T', 'toan', 8, %s, %s, %s) RETURNING id",
                      (f"sgk/{status}-{error}.pdf", status, error)).fetchone()[0]


def test_failed_iff_error(db):
    add_document(db, "failed", "parse: broken")
    add_document(db, "ready")
    with pytest.raises(psycopg.errors.CheckViolation):
        add_document(db, "failed", None)
    with pytest.raises(psycopg.errors.CheckViolation):
        add_document(db, "ready", "leftover error")
