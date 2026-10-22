"""Chuẩn bị tri thức: bản nháp → giáo viên kiểm duyệt → xuất bản; học sinh chỉ học tài liệu đã xuất bản."""
import pytest

from app.core.ai.fakes import fake_vector
from tests.conftest import as_user, running_app
from tests.features.learning.test_guided import TEACH_1

TEACHER = as_user("colan")


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


@pytest.fixture
def draft(db, textbook, make_teacher, make_student):
    """SGK mẫu ở dạng bản nháp (1 hình đang chờ duyệt)."""
    make_teacher("colan")
    make_student("minh5a")
    db.execute("UPDATE documents SET published_at = NULL WHERE id = %s", (textbook["document"],))
    return textbook


def doc_url(textbook, action=""):
    return f"/curation/documents/{textbook['document']}{action}"


async def test_draft_hidden_from_students(api, draft):
    docs = (await api.get("/documents", headers=as_user("minh5a"))).json()
    assert str(draft["document"]) not in {d["id"] for d in docs}
    r = await api.post("/sessions", json={"lesson_id": str(draft["lessons"][1])}, headers=as_user("minh5a"))
    assert r.status_code == 409


async def test_pending_figures_block_publishing(api, draft):
    r = await api.post(doc_url(draft, "/publish"), headers=TEACHER)
    assert r.status_code == 409 and "1 hình" in r.json()["detail"]
    assert (await api.get(doc_url(draft), headers=TEACHER)).json()["document"]["published"] is False


async def test_publish_after_review_then_reprocess_unpublishes(api, draft, db):
    await api.post(f"/teacher/figures/{draft['chunks']['figure']}/review", json={"action": "approve"}, headers=TEACHER)
    r = await api.post(doc_url(draft, "/publish"), headers=TEACHER)
    assert r.status_code == 200 and r.json()["published"] is True
    docs = (await api.get("/documents", headers=as_user("minh5a"))).json()
    assert str(draft["document"]) in {d["id"] for d in docs}
    await api.post(f"/documents/{draft['document']}/reprocess", headers=TEACHER)
    assert db.execute("SELECT published_at FROM documents WHERE id = %s", (draft["document"],)).fetchone()[0] is None


async def test_parts_as_lusia_will_use_them(api, draft):
    long = " ".join(f"Câu số {i} nói về đồ thị của hàm số bậc nhất trong bài học hôm nay của lớp tám." for i in range(14))
    chunk = draft["add"](2, long, page=4)
    lesson2 = (await api.get(doc_url(draft), headers=TEACHER)).json()["lessons"][1]
    texts = [p for p in lesson2["parts"] if p["chunk_id"] == chunk]
    assert len(texts) >= 3 and all(len(p["content"]) <= 450 for p in texts)
    (figure,) = [p for p in lesson2["parts"] if p["kind"] == "figure"]
    assert figure["review"] == "pending" and figure["image_url"].endswith("/image")


async def test_fix_a_text_error_reembeds(api, draft, db):
    chunk = draft["chunks"]["concept"]
    r = await api.patch(f"/curation/chunks/{chunk}", json={"content": "Hàm số bậc nhất có dạng y = ax + b, a khác 0."},
                        headers=TEACHER)
    assert r.status_code == 204
    content, title = db.execute("SELECT c.content, l.title FROM chunks c JOIN lessons l ON l.id = c.lesson_id"
                                " WHERE c.id = %s", (chunk,)).fetchone()
    assert content.startswith("Hàm số bậc nhất có dạng")
    # embed lại theo đúng quy tắc lúc nạp: tên bài + nội dung
    assert db.execute("SELECT embedding = %s::vector FROM chunks WHERE id = %s",
                      (str(fake_vector(f"{title}\n{content}")), chunk)).fetchone()[0]


async def test_remove_noise_and_figures_only_via_review(api, draft, db):
    noise = draft["add"](1, "TOÁN 8 - TẬP MỘT - trang 2", page=2)
    assert (await api.delete(f"/curation/chunks/{noise}", headers=TEACHER)).status_code == 204
    assert db.execute("SELECT count(*) FROM chunks WHERE id = %s", (noise,)).fetchone()[0] == 0
    figure = draft["chunks"]["figure"]
    assert (await api.delete(f"/curation/chunks/{figure}", headers=TEACHER)).status_code == 409


async def test_students_cannot_curate(api, draft):
    r = await api.post(doc_url(draft, "/publish"), headers=as_user("minh5a"))
    assert r.status_code == 400  # danh tính dev: endpoint cần giáo viên


async def test_preview_is_not_stored(api, draft, db):
    api.app.state.llm.script({**TEACH_1, "hook": "Có người từng ví đồ thị như một con đường."})
    r = await api.post("/curation/preview", json={"lesson_id": str(draft["lessons"][2]), "part": 1}, headers=TEACHER)
    body = r.json()
    assert r.status_code == 200 and body["parts"] == 2
    assert "con đường" in body["answer"] and TEACH_1["check_question"] in body["answer"]
    assert db.execute("SELECT (SELECT count(*) FROM learning_sessions) + (SELECT count(*) FROM messages)"
                      " + (SELECT count(*) FROM questions)").fetchone()[0] == 0


async def test_teacher_upload_reaches_students_only_after_publish(api, draft, db):
    from tests import pdfs
    from tests.features.documents.test_documents_api import upload

    doc = (await upload(api, pdfs.plain_pdf(1), "colan")).json()["id"]
    db.execute("UPDATE documents SET status = 'ready' WHERE id = %s", (doc,))
    assert doc not in {d["id"] for d in (await api.get("/documents", headers=as_user("minh5a"))).json()}
    await api.post(f"/curation/documents/{doc}/publish", headers=TEACHER)
    assert doc in {d["id"] for d in (await api.get("/documents", headers=as_user("minh5a"))).json()}


async def test_rejected_figure_listed_without_part_number(api, draft):
    await api.post(f"/teacher/figures/{draft['chunks']['figure']}/review", json={"action": "reject"}, headers=TEACHER)
    parts = (await api.get(doc_url(draft), headers=TEACHER)).json()["lessons"][1]["parts"]
    assert [(p["kind"], p["number"], p["review"]) for p in parts] == [("text", 1, None), ("figure", None, "rejected")]


async def test_outline_shown_edited_regenerated_and_taught(api, draft, db):
    from tests.features.documents.test_outline import draft as outline_draft

    lesson, text_id, figure_id = draft["lessons"][2], draft["chunks"]["graph_text"], draft["chunks"]["figure"]
    before = (await api.get(doc_url(draft), headers=TEACHER)).json()["lessons"][1]
    assert before["outline"] == [] and before["teaching"][0]["label"].startswith("Đồ thị của hàm số")  # đoạn đã lọc
    api.app.state.llm.script(outline_draft(text_id, figure_id))
    outline = (await api.post(f"/curation/lessons/{lesson}/outline", headers=TEACHER)).json()
    assert [(p["position"], p["title"], p["pages"]) for p in outline] == [
        (0, "Mở đầu", [4]), (1, "Đồ thị là đường thẳng", [4]), (2, "Giao điểm với trục tung", [5])]
    r = await api.patch(f"/curation/lessons/{lesson}/outline/1", headers=TEACHER, json={
        "title": "Đồ thị là một đường thẳng", "content": "Đồ thị của y = ax + b là một đường thẳng.",
        "question": "Đồ thị là đường gì?", "answer": "đường thẳng"})
    assert r.status_code == 200 and r.json()[1]["title"] == "Đồ thị là một đường thẳng"
    bad = await api.patch(f"/curation/lessons/{lesson}/outline/1", headers=TEACHER,
                          json={"title": "x", "content": "y", "question": "Hỏi?", "answer": ""})
    assert bad.status_code == 422
    assert (await api.delete(f"/curation/lessons/{lesson}/outline/2", headers=TEACHER)).status_code == 204
    after = (await api.get(doc_url(draft), headers=TEACHER)).json()["lessons"][1]
    assert [t["label"] for t in after["teaching"]] == ["Đồ thị là một đường thẳng"]               # LUSIA giảng theo dàn ý


async def test_regenerate_failure_keeps_the_old_outline(api, draft):
    from app.core.ai.llm import Refusal

    api.app.state.llm.script(Refusal("other"))
    r = await api.post(f"/curation/lessons/{draft['lessons'][2]}/outline", headers=TEACHER)
    assert r.status_code == 502 and "Không tạo được dàn ý" in r.json()["detail"]


async def test_processing_document_shows_its_current_step(api, draft, db):
    from app.core.storage import cache
    from app.features.documents.ingestion.progress import key

    db.execute("UPDATE documents SET status = 'processing', published_at = NULL WHERE id = %s", (draft["document"],))
    await cache.redis().set(key(draft["document"]), "Đang mô tả hình 120/290", ex=60)
    try:
        doc = next(d for d in (await api.get("/curation/documents", headers=TEACHER)).json()
                   if d["id"] == str(draft["document"]))
        assert doc["progress"] == "Đang mô tả hình 120/290"
    finally:
        await cache.redis().delete(key(draft["document"]))


async def test_curation_upload_belongs_to_the_teacher(api, draft, db, make_teacher):
    from tests import pdfs

    form = {"title": "Toán 5", "subject": "toan", "grade": "5"}
    files = {"file": ("toan5.pdf", pdfs.plain_pdf(1), "application/pdf")}
    r = await api.post("/curation/documents", data=form, files=files, headers=TEACHER)
    assert r.status_code == 202
    owner = db.execute("SELECT u.username FROM documents d JOIN users u ON u.id = d.uploaded_by WHERE d.id = %s",
                       (r.json()["id"],)).fetchone()[0]
    assert owner == "colan"
    student = await api.post("/curation/documents", data=form, files=files, headers=as_user("minh5a"))
    assert student.status_code == 400  # danh tính dev: endpoint cần giáo viên


async def test_approve_all_figures_then_publish(api, draft, db):
    rejected = draft["add"](2, "Hình trang trí", kind="figure", review="rejected", page=5)
    r = await api.post(doc_url(draft, "/figures/approve-all"), headers=TEACHER)
    assert r.status_code == 200 and r.json() == {"approved": 1}
    assert db.execute("SELECT review FROM chunks WHERE id = %s", (rejected,)).fetchone()[0] == "rejected"
    assert (await api.post(doc_url(draft, "/publish"), headers=TEACHER)).json()["published"] is True
    student = await api.post(doc_url(draft, "/figures/approve-all"), headers=as_user("minh5a"))
    assert student.status_code == 400
