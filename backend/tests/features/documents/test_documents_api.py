from uuid import UUID

import pytest

from app.core import jobs
from app.core.ai.fakes import FakeEmbeddings, FakeLLM
from app.core.storage.files import LocalFileStore
from app.features.documents.ingestion.pipeline import Deps, process_document
from tests import pdfs
from tests.conftest import as_user, running_app
from tests.features.documents.ingestion.conftest import GRAPH

FORM = {"title": "Phiếu học tập", "subject": "toan", "grade": "8"}


@pytest.fixture
async def api(tmp_path, test_database):
    async with running_app(files_dir=tmp_path) as client:
        pool = await jobs.queue()
        await pool.flushdb()
        yield client
        await pool.flushdb()


def deps_for(client, *replies):
    settings = client.app.state.settings
    return Deps(settings, FakeLLM(settings).script(*replies), FakeEmbeddings(), LocalFileStore(settings.files_dir))


async def upload(client, data: bytes, user="minh8a", **extra):
    return await client.post("/documents", headers=as_user(user), data={**FORM, **extra},
                             files={"file": ("bai.pdf", data, "application/pdf")})


async def queued(client):
    pool = await jobs.queue()
    return [j.function for j in await pool.queued_jobs()]


# ---------- upload ----------

@pytest.mark.parametrize("data, status, message", [
    (pdfs.png(), 422, "not a PDF"),
    (pdfs.encrypted_pdf(), 422, "encrypted"),
])
async def test_upload_rejects_bad_files(api, make_student, db, data, status, message):
    make_student("minh8a")
    r = await upload(api, data)
    assert r.status_code == status and message in r.json()["detail"]
    assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


async def test_upload_too_large_and_too_many_pages(tmp_path, test_database, make_student, db):
    make_student("minh8a")
    async with running_app(files_dir=tmp_path, max_upload_mb=1, max_pages=4) as client:
        big = pdfs.plain_pdf(1) + b"%" * (1024 * 1024)
        assert (await upload(client, big)).status_code == 413
        r = await upload(client, pdfs.many_pages_pdf(5))
        assert r.status_code == 422 and "limit 4" in r.json()["detail"]
    assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


async def test_student_uploads_a_handout(api, make_student, make_teacher, db):
    student = make_student("minh8a")
    teacher = make_teacher("colan")
    r = await upload(api, pdfs.plain_pdf(3), uploaded_by=str(teacher))  # body không đổi được người tải lên
    assert r.status_code == 202 and r.json()["status"] == "processing"
    kind, uploaded_by, status, key = db.execute(
        "SELECT kind, uploaded_by, status, storage_key FROM documents WHERE id = %s", (r.json()["id"],)).fetchone()
    assert (kind, uploaded_by, status) == ("upload", student, "processing")
    assert key == f"uploads/{student}/{r.json()['id']}.pdf"
    assert await queued(api) == ["ingest_document"]


# ---------- read ----------

async def ready_document(client, data=None, user="minh8a", replies=(GRAPH,)):
    r = await upload(client, data or pdfs.lessons_pdf(), user)
    doc_id = UUID(r.json()["id"])
    await process_document(doc_id, deps_for(client, *replies))
    return doc_id


async def test_document_summary(api, make_student):
    make_student("minh8a")
    doc_id = await ready_document(api)
    r = await api.get(f"/documents/{doc_id}", headers=as_user("minh8a"))
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ready" and body["page_count"] == 7
    assert (body["lessons"], body["figure_chunks"], body["pending_figures"], body["skipped_figures"]) == (2, 1, 1, 0)
    assert body["text_chunks"] > 0 and body["error"] is None


async def test_unknown_ids_are_404(api, make_student):
    make_student("minh8a")
    missing = "00000000-0000-0000-0000-000000000000"
    for path in (f"/documents/{missing}", f"/documents/{missing}/file", f"/documents/{missing}/lessons",
                 "/figures/999999/image"):
        assert (await api.get(path)).status_code == 404, path


async def test_list_shows_textbooks_and_own_uploads_only(api, make_student, db):
    make_student("minh8a")
    make_student("hana8a", language="ja")
    mine = (await upload(api, pdfs.plain_pdf(1), "minh8a")).json()["id"]
    await upload(api, pdfs.plain_pdf(1), "hana8a")
    db.execute("INSERT INTO documents (kind, title, subject, grade, storage_key, status, published_at) VALUES"
               " ('textbook', 'SGK Toán 8', 'toan', 8, 'sgk/x.pdf', 'ready', now()),"
               " ('textbook', 'SGK Văn 9', 'ngu_van', 9, 'sgk/y.pdf', 'ready', now()),"
               " ('textbook', 'SGK nháp', 'toan', 8, 'sgk/z.pdf', 'ready', NULL)")  # bản nháp: học sinh không thấy
    titles = {d["title"] for d in (await api.get("/documents", headers=as_user("minh8a"))).json()}
    assert titles == {"SGK Toán 8", "SGK Văn 9", "Phiếu học tập"}
    toan8 = (await api.get("/documents?subject=toan&grade=8", headers=as_user("minh8a"))).json()
    assert {d["title"] for d in toan8} == {"SGK Toán 8", "Phiếu học tập"} and mine in {d["id"] for d in toan8}


async def test_download_file_lessons_and_figure_image(api, make_student, db):
    make_student("minh8a")
    data = pdfs.lessons_pdf()
    doc_id = await ready_document(api, data)
    file = await api.get(f"/documents/{doc_id}/file")
    assert file.headers["content-type"] == "application/pdf" and file.content == data
    lessons = (await api.get(f"/documents/{doc_id}/lessons")).json()
    assert [(l["position"], l["page_start"], l["page_end"]) for l in lessons] == [(1, 2, 4), (2, 5, 7)]
    figure_id, text_id = (db.execute("SELECT min(id) FILTER (WHERE kind = 'figure'), min(id) FILTER (WHERE kind = 'text')"
                                     " FROM chunks").fetchone())
    image = await api.get(f"/figures/{figure_id}/image")
    assert image.headers["content-type"] == "image/png" and image.content.startswith(b"\x89PNG")
    assert (await api.get(f"/figures/{text_id}/image")).status_code == 404


# ---------- lessons ----------

async def test_fix_a_lesson_boundary(api, make_student, make_teacher, db):
    make_student("minh8a")
    make_teacher("colan")
    doc_id = await ready_document(api)
    (l1, l2) = (await api.get(f"/documents/{doc_id}/lessons")).json()
    await (await jobs.queue()).flushdb()
    body = [{"id": l1["id"], "title": l1["title"], "page_start": 2, "page_end": 3},
            {"id": l2["id"], "title": l2["title"], "page_start": 4, "page_end": 7}]
    r = await api.put(f"/documents/{doc_id}/lessons", json=body, headers=as_user("colan"))
    assert r.status_code == 202
    assert [(l["id"], l["page_start"], l["page_end"]) for l in r.json()] == [(l1["id"], 2, 3), (l2["id"], 4, 7)]
    assert db.execute("SELECT status FROM documents WHERE id = %s", (doc_id,)).fetchone()[0] == "processing"
    assert await queued(api) == ["ingest_document"]
    await process_document(doc_id, deps_for(api, GRAPH))   # worker dựng lại chunk theo bài mới
    page4 = db.execute("SELECT DISTINCT lesson_id FROM chunks WHERE document_id = %s AND page = 4", (doc_id,)).fetchall()
    assert page4 == [(UUID(l2["id"]),)]


async def test_lesson_with_quiz_results_cannot_be_deleted(api, make_student, make_teacher, db):
    student = make_student("minh8a")
    make_teacher("colan")
    doc_id = await ready_document(api)
    (l1, l2) = (await api.get(f"/documents/{doc_id}/lessons")).json()
    db.execute("INSERT INTO quizzes (student_id, lesson_id) VALUES (%s, %s)", (student, l2["id"]))
    chunks_before = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    body = [{"id": l1["id"], "title": l1["title"], "page_start": 2, "page_end": 7}]
    r = await api.put(f"/documents/{doc_id}/lessons", json=body, headers=as_user("colan"))
    assert r.status_code == 409 and l2["title"] in r.json()["detail"]
    assert (await api.get(f"/documents/{doc_id}/lessons")).json() == [l1, l2]
    assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == chunks_before


@pytest.mark.parametrize("body", [
    [{"title": "A", "page_start": 0, "page_end": 3}],
    [{"title": "A", "page_start": 2, "page_end": 5}, {"title": "B", "page_start": 5, "page_end": 7}],
    [{"title": "A", "page_start": 6, "page_end": 3}],
])
async def test_invalid_lesson_ranges(api, make_student, make_teacher, body):
    make_student("minh8a")
    make_teacher("colan")
    doc_id = await ready_document(api)
    assert (await api.put(f"/documents/{doc_id}/lessons", json=body, headers=as_user("colan"))).status_code == 422


async def test_reprocess_requeues(api, make_student, make_teacher, db):
    make_student("minh8a")
    make_teacher("colan")
    doc_id = await ready_document(api)
    await (await jobs.queue()).flushdb()
    r = await api.post(f"/documents/{doc_id}/reprocess", headers=as_user("colan"))
    assert r.status_code == 202 and await queued(api) == ["ingest_document"]
    assert db.execute("SELECT status, error FROM documents WHERE id = %s", (doc_id,)).fetchone() == ("processing", None)


async def test_student_cannot_edit_lessons(api, make_student):
    make_student("minh8a")
    doc_id = await ready_document(api)
    r = await api.post(f"/documents/{doc_id}/reprocess", headers=as_user("minh8a"))
    assert r.status_code == 400  # danh tính dev: endpoint cần giáo viên
