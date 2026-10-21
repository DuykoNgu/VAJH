import uuid

import pytest

from app.config import get_settings
from app.core.ai.fakes import FakeEmbeddings, FakeLLM
from app.core.storage import relational
from app.core.storage.files import LocalFileStore
from app.features.documents.ingestion.pipeline import Deps

GRAPH = {"kind": "graph", "description": "Đồ thị hàm số y bằng hai x cộng một là một đường thẳng đi lên."}


@pytest.fixture
async def pool(test_database):
    await relational.open_pool(test_database)
    yield
    await relational.close_pool()


@pytest.fixture
def deps(tmp_path):
    settings = get_settings().model_copy(update={"files_dir": tmp_path})
    return Deps(settings, FakeLLM(settings), FakeEmbeddings(), LocalFileStore(tmp_path))


@pytest.fixture
def new_document(db, deps):
    async def _new(data: bytes, *, title="Toán 8", uploaded_by=None):
        doc_id = uuid.uuid4()
        kind = "upload" if uploaded_by else "textbook"
        key = f"uploads/{uploaded_by}/{doc_id}.pdf" if uploaded_by else f"sgk/{doc_id}.pdf"
        db.execute("INSERT INTO documents (id, kind, title, subject, grade, storage_key, uploaded_by)"
                   " VALUES (%s, %s, %s, 'toan', 8, %s, %s)", (doc_id, kind, title, key, uploaded_by))
        await deps.files.put(key, data, "application/pdf")
        return doc_id
    return _new
