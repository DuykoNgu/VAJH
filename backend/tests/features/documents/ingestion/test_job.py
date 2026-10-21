import os

import pytest
from arq.connections import RedisSettings
from arq.worker import Worker

from app import worker
from app.core import jobs
from tests import pdfs
from tests.features.documents.ingestion.conftest import GRAPH
from tests.features.documents.ingestion.test_pipeline import FailingLLM, document

pytestmark = pytest.mark.usefixtures("pool")


@pytest.fixture
async def queue():
    jobs.configure_queue(os.environ["REDIS_URL"])
    pool = await jobs.queue()
    await pool.flushdb()
    yield
    await pool.flushdb()
    await jobs.close_queue()


async def run_worker(deps):
    w = Worker(functions=worker.WorkerSettings.functions, redis_settings=RedisSettings.from_dsn(os.environ["REDIS_URL"]),
               burst=True, poll_delay=0.05, max_tries=worker.MAX_TRIES, handle_signals=False, ctx={"deps": deps})
    await w.main()
    await w.close()


async def test_enqueued_document_processed_to_ready(db, deps, new_document, queue):
    doc_id = await new_document(pdfs.lessons_pdf())
    deps.llm.script(GRAPH)
    await jobs.enqueue("ingest_document", str(doc_id))
    await run_worker(deps)
    assert document(db, doc_id)[0] == "ready"


async def test_broken_pdf_fails_without_retry(db, deps, new_document, queue):
    doc_id = await new_document(b"%PDF-1.7 not really a pdf")
    deps.llm = FailingLLM(deps.settings)
    await jobs.enqueue("ingest_document", str(doc_id))
    await run_worker(deps)
    status, *_, error = document(db, doc_id)
    assert status == "failed" and error.startswith("parse: unreadable PDF") and deps.llm.count == 0


async def test_final_try_marks_failed(db, deps, new_document, queue, monkeypatch):
    monkeypatch.setattr(worker, "RETRY_BASE_S", 0.01)
    doc_id = await new_document(pdfs.special_pages_pdf())
    deps.llm = FailingLLM(deps.settings)
    await jobs.enqueue("ingest_document", str(doc_id))
    await run_worker(deps)
    status, *_, error = document(db, doc_id)
    assert status == "failed" and error.startswith("ocr: ")
    assert deps.llm.count >= worker.MAX_TRIES  # đã thử lại trước khi bỏ cuộc
