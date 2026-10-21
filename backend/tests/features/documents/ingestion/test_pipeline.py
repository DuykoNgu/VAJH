import pytest

from app.core.ai.fakes import FakeLLM
from app.core.ai.llm import Refusal
from app.features.documents.ingestion.pipeline import (
    IngestionError,
    mark_failed,
    process_document,
)
from tests import pdfs
from tests.features.documents.ingestion.conftest import GRAPH

pytestmark = pytest.mark.usefixtures("pool")


class FailingLLM(FakeLLM):
    """Lỗi ở lời gọi thứ `fail_on` (1-based) hoặc mọi lời gọi nếu fail_on=None."""

    def __init__(self, settings, fail_on=None):
        super().__init__(settings)
        self.fail_on, self.count = fail_on, 0

    async def complete(self, route, messages, *, system=None, schema=None):
        self.count += 1
        if self.fail_on is None or self.count == self.fail_on:
            raise RuntimeError("provider down")
        return await super().complete(route, messages, system=system, schema=schema)


def document(db, doc_id):
    return db.execute("SELECT status, page_count, processed_pages, skipped_figures, error FROM documents"
                      " WHERE id = %s", (doc_id,)).fetchone()


def chunks(db, doc_id):
    return db.execute("SELECT kind, lesson_id, page, content, image_key, review, vector_dims(embedding)"
                      " FROM chunks WHERE document_id = %s ORDER BY id", (doc_id,)).fetchall()


def lessons(db, doc_id):
    return db.execute("SELECT id, title, page_start, page_end FROM lessons WHERE document_id = %s ORDER BY position",
                      (doc_id,)).fetchall()


async def test_successful_processing(db, deps, new_document):
    doc_id = await new_document(pdfs.lessons_pdf())
    deps.llm.script(GRAPH)
    summary = await process_document(doc_id, deps)
    assert document(db, doc_id) == ("ready", 7, 7, 0, None)
    (bai1, bai2) = lessons(db, doc_id)
    assert (bai1[2:], bai2[2:]) == ((2, 4), (5, 7))
    rows = chunks(db, doc_id)
    texts = [r for r in rows if r[0] == "text"]
    (figure,) = [r for r in rows if r[0] == "figure"]
    assert texts and {r[6] for r in rows} == {1024}
    assert figure[1] == bai2[0] and figure[2] == 6 and figure[5] == "pending" and figure[3] == GRAPH["description"]
    assert (await deps.files.get(figure[4])).startswith(b"\x89PNG")  # ảnh đã lưu
    assert texts[0][1] is None and texts[0][2] == 1  # trang bìa ngoài mọi bài
    assert (summary.lesson_source, summary.ocr_pages, summary.figure_chunks) == ("bookmarks", 0, 1)
    assert [c["route"] for c in deps.llm.calls] == ["vision_offline"]


async def test_first_run_failure_leaves_no_chunks(db, deps, new_document):
    doc_id = await new_document(pdfs.special_pages_pdf())
    deps.llm = FailingLLM(deps.settings)
    with pytest.raises(IngestionError) as e:
        await process_document(doc_id, deps)
    assert e.value.step == "ocr" and "provider down" in str(e.value)
    await mark_failed(doc_id, str(e.value))
    assert document(db, doc_id)[0] == "failed" and document(db, doc_id)[4].startswith("ocr: ")
    assert chunks(db, doc_id) == [] and lessons(db, doc_id) == []


async def test_reprocess_failure_keeps_previous_content(db, deps, new_document):
    doc_id = await new_document(pdfs.special_pages_pdf())
    deps.llm.script("Trang TCVN3 (OCR)", "Trang scan (OCR)", {"entries": []})
    await process_document(doc_id, deps)
    before_chunks, before_lessons = chunks(db, doc_id), lessons(db, doc_id)
    deps.llm = FailingLLM(deps.settings)
    with pytest.raises(IngestionError):
        await process_document(doc_id, deps)
    await mark_failed(doc_id, "ocr: provider down")
    assert chunks(db, doc_id) == before_chunks and lessons(db, doc_id) == before_lessons
    assert document(db, doc_id)[0] == "failed"


async def test_reprocess_twice_is_idempotent(db, deps, new_document):
    doc_id = await new_document(pdfs.lessons_pdf())
    deps.llm.script(GRAPH, GRAPH, GRAPH)
    await process_document(doc_id, deps)
    first_lessons, first_count = lessons(db, doc_id), len(chunks(db, doc_id))
    old_key = [r[4] for r in chunks(db, doc_id) if r[0] == "figure"][0]
    await process_document(doc_id, deps)
    await process_document(doc_id, deps)
    assert lessons(db, doc_id) == first_lessons and len(chunks(db, doc_id)) == first_count
    new_key = [r[4] for r in chunks(db, doc_id) if r[0] == "figure"][0]
    assert new_key != old_key and not (deps.settings.files_dir / old_key).exists()
    assert (deps.settings.files_dir / new_key).exists()


async def test_one_of_three_figures_failing(db, deps, new_document):
    doc_id = await new_document(pdfs.three_figures_pdf())
    deps.llm = FailingLLM(deps.settings, fail_on=2).script({"entries": []}, GRAPH, GRAPH)
    summary = await process_document(doc_id, deps)
    status, _, _, skipped, _ = document(db, doc_id)
    assert (status, skipped, summary.figure_chunks) == ("ready", 1, 2)
    assert [r for r in chunks(db, doc_id) if r[0] == "text"]


async def test_decorative_figures_are_not_stored(db, deps, new_document):
    doc_id = await new_document(pdfs.lessons_pdf())
    deps.llm.script({"kind": "decorative", "description": "Hoa văn"})
    summary = await process_document(doc_id, deps)
    assert summary.decorative_figures == 1 and [r for r in chunks(db, doc_id) if r[0] == "figure"] == []


async def test_figures_outside_every_lesson_are_skipped(db, deps, new_document):
    import pymupdf

    doc = pymupdf.open(stream=pdfs.lessons_pdf(), filetype="pdf")
    pdfs.add_graph(doc[0])  # hình trên trang bìa (ngoài mọi bài học); bìa ít chữ + có hình → OCR
    doc_id = await new_document(doc.tobytes())
    deps.llm.script("Toán 8 - Tập 2. Sách giáo khoa", GRAPH)
    summary = await process_document(doc_id, deps)
    assert summary.figure_chunks == 1 and [r[2] for r in chunks(db, doc_id) if r[0] == "figure"] == [6]
    assert [c["route"] for c in deps.llm.calls] == ["document", "vision_offline"]   # chỉ mô tả hình trong bài


async def test_outline_generated_after_import(db, deps, new_document):
    deps.settings = deps.settings.model_copy(update={"outline_on_ingest": True})
    doc_id = await new_document(pdfs.lessons_pdf())
    point = {"title": "Ý chính", "content": "Hàm số bậc nhất là hàm số y = ax + b.", "question": "a phải thế nào?",
             "answer": "khác 0", "sources": []}
    deps.llm.script(GRAPH, {"opening": "", "opening_sources": [], "points": [point]}, Refusal("other"))
    summary = await process_document(doc_id, deps)
    assert document(db, doc_id)[0] == "ready" and summary.outlined_lessons == 1     # bài 2 lỗi: vẫn sẵn sàng
    assert [c["route"] for c in deps.llm.calls] == ["vision_offline", "outline", "outline"]
    assert db.execute("SELECT count(*) FROM lesson_points").fetchone()[0] == 1


async def test_progress_reported_after_ocr_and_cleared(db, deps, new_document, monkeypatch):
    from app.features.documents.ingestion import progress

    reported = []

    async def report(self, text):
        reported.append(text)

    monkeypatch.setattr(progress.Progress, "report", report)
    doc_id = await new_document(pdfs.lessons_pdf())
    deps.llm.script(GRAPH)
    await process_document(doc_id, deps)
    assert "Đang chia bài theo mục lục" in reported and "Đang mô tả hình 1/1" in reported
    assert reported[-1] == "Đang lưu" and any(r.startswith("Đang tìm hình trang") for r in reported)
