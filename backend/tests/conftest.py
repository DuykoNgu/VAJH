"""Test harness: một database Postgres riêng (lusia_test), tạo lại mỗi lần chạy, xoá dữ liệu sau mỗi test.

Không bao giờ dùng DATABASE_URL trong backend/.env (có thể là Neon) - chỉ TEST_DATABASE_URL.
"""
import os
from urllib.parse import urlsplit, urlunsplit

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://lusia:lusia@localhost:5432/lusia_test")
os.environ.update(
    APP_ENV="test",
    AUTH_MODE="dev",
    DATABASE_URL=TEST_DATABASE_URL,
    DATABASE_URL_UNPOOLED=TEST_DATABASE_URL,
    REDIS_URL=os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
    LLM_PROVIDER="fake",
    EMBEDDING_PROVIDER="fake",
    LOCAL_OCR="false",                      # test tất định: không gọi OCR của macOS / model bố cục thật
    LAYOUT_MODEL_PATH="/nonexistent/doclayout.pt",
    TRACE_PAYLOADS="all",                   # test lấy mẫu tự đổi sang "sampled"
    OUTLINE_ON_INGEST="false",              # test pipeline bật riêng khi cần
    PREFETCH_PARTS="false",                 # soạn sẵn chạy ngầm sẽ lấy mất câu trả lời giả lập theo kịch bản
)

import psycopg  # noqa: E402
import pytest  # noqa: E402

from app.migrate import migrate  # noqa: E402


def _admin_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path="/postgres"))


@pytest.fixture(scope="session", autouse=True)
def test_database():
    name = urlsplit(TEST_DATABASE_URL).path.lstrip("/")
    assert name.endswith("_test"), f"refusing to recreate a non-test database: {name}"
    with psycopg.connect(_admin_url(TEST_DATABASE_URL), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    migrate(TEST_DATABASE_URL)
    yield TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def clean_tables(test_database):
    yield
    with psycopg.connect(test_database, autocommit=True) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migrations'")]
        if tables:
            conn.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")


@pytest.fixture
def db(test_database):
    """Kết nối đồng bộ tới DB test (autocommit) để chuẩn bị/kiểm tra dữ liệu."""
    with psycopg.connect(test_database, autocommit=True) as conn:
        yield conn


from contextlib import asynccontextmanager  # noqa: E402

import httpx  # noqa: E402


@asynccontextmanager
async def running_app(**overrides):
    """App thật (có lifespan) + client HTTP; overrides thay giá trị cấu hình cho riêng test đó."""
    from app.config import get_settings
    from app.main import create_app

    settings = get_settings().model_copy(update=overrides)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            client.app = app
            yield client


@pytest.fixture
async def client(test_database):
    async with running_app() as c:
        yield c


# ---------- Danh tính test (TEST_USER): mỗi test tự tạo người dùng, không phụ thuộc seed ----------
from app.core.identity import DEV_USER_HEADER, NO_CREDENTIAL, UserContext, current_student, current_teacher, current_user  # noqa: E402,I001


@pytest.fixture
def make_student(db):
    def _make(username="minh8a", *, grade=8, language="vi", speech_rate=1.0, full_name="Em Minh"):
        uid = db.execute("INSERT INTO users (full_name, username, password_hash) VALUES (%s, %s, %s) RETURNING id",
                         (full_name, username, NO_CREDENTIAL)).fetchone()[0]
        db.execute("INSERT INTO students (user_id, grade, language, speech_rate) VALUES (%s, %s, %s, %s)",
                   (uid, grade, language, speech_rate))
        return uid
    return _make


@pytest.fixture
def make_teacher(db):
    def _make(username="colan", *, full_name="Cô Lan"):
        uid = db.execute("INSERT INTO users (full_name, username, password_hash) VALUES (%s, %s, %s) RETURNING id",
                         (full_name, username, NO_CREDENTIAL)).fetchone()[0]
        db.execute("INSERT INTO teachers (user_id) VALUES (%s)", (uid,))
        return uid
    return _make


def as_user(username: str) -> dict:
    """Header chọn người dùng dev cho một request."""
    return {DEV_USER_HEADER: username}


def override_identity(app, user: UserContext) -> None:
    """Bỏ qua provider: mọi dependency danh tính trả về `user` (dùng cho test service/endpoint)."""
    for dep in (current_user, current_student, current_teacher):
        app.dependency_overrides[dep] = lambda user=user: user


# ---------- Nội dung SGK mẫu trong DB (bài 1: chữ; bài 2: chữ + một hình chờ duyệt) ----------
GRAPH_DESCRIPTION = "Đồ thị hàm số y bằng hai x cộng một là đường thẳng đi lên, cắt trục tung tại điểm một."


@pytest.fixture
def textbook(db):
    import uuid as _uuid

    from app.core.ai.fakes import fake_vector

    doc = _uuid.uuid4()
    db.execute("INSERT INTO documents (id, kind, title, subject, grade, storage_key, status, published_at) VALUES"
               " (%s, 'textbook', 'Toán 8', 'toan', 8, %s, 'ready', now())", (doc, f"sgk/{doc}.pdf"))
    lessons = {}
    for pos, title in enumerate(["Bài 1. Hàm số bậc nhất", "Bài 2. Đồ thị của hàm số bậc nhất"], 1):
        lessons[pos] = db.execute("INSERT INTO lessons (document_id, position, title, page_start, page_end)"
                                  " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                  (doc, pos, title, pos * 2, pos * 2 + 1)).fetchone()[0]

    def add(lesson, content, kind="text", review=None, page=2):
        return db.execute(
            "INSERT INTO chunks (document_id, lesson_id, page, kind, content, embedding, image_key, review, reviewed_at)"
            " VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s) RETURNING id",
            (doc, lessons[lesson], page, kind, content, str(fake_vector(content)),
             f"fig/{doc}/r/{page}-1.png" if kind == "figure" else None, review,
             None if review in (None, "pending") else "2026-10-04")).fetchone()[0]

    chunks = {
        "concept": add(1, "Hàm số bậc nhất là hàm số y = ax + b với a khác 0.", page=2),
        "graph_text": add(2, "Đồ thị của hàm số y = ax + b là một đường thẳng.", page=4),
        "figure": add(2, GRAPH_DESCRIPTION, kind="figure", review="pending", page=5),
    }
    return {"document": doc, "lessons": lessons, "chunks": chunks, "add": add}
