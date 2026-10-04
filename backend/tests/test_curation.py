"""Chuẩn bị tri thức: bản nháp → giáo viên kiểm duyệt → xuất bản; học sinh chỉ học tài liệu đã xuất bản."""
import pytest

from app.ai.fakes import fake_vector
from tests.conftest import as_user, running_app
from tests.test_guided import TEACH_1

TEACHER = as_user("colan")


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


@pytest.fixture
def draft(db, textbook, make_teacher, make_student):
    """SGK mẫu ở dạng bản nháp (1 hình đang chờ duyệt)."""
    make_teacher("colan")
    make_student("minh8a")
    db.execute("UPDATE documents SET published_at = NULL WHERE id = %s", (textbook["document"],))
    return textbook


def doc_url(textbook, action=""):
    return f"/curation/documents/{textbook['document']}{action}"


async def test_draft_hidden_from_students(api, draft):
    docs = (await api.get("/documents", headers=as_user("minh8a"))).json()
    assert str(draft["document"]) not in {d["id"] for d in docs}
    r = await api.post("/sessions", json={"lesson_id": str(draft["lessons"][1])}, headers=as_user("minh8a"))
    assert r.status_code == 409


async def test_pending_figures_block_publishing(api, draft):
    r = await api.post(doc_url(draft, "/publish"), headers=TEACHER)
    assert r.status_code == 409 and "1 hình" in r.json()["detail"]
    assert (await api.get(doc_url(draft), headers=TEACHER)).json()["document"]["published"] is False


async def test_publish_after_review_then_reprocess_unpublishes(api, draft, db):
    await api.post(f"/teacher/figures/{draft['chunks']['figure']}/review", json={"action": "approve"}, headers=TEACHER)
    r = await api.post(doc_url(draft, "/publish"), headers=TEACHER)
    assert r.status_code == 200 and r.json()["published"] is True
    docs = (await api.get("/documents", headers=as_user("minh8a"))).json()
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
    content = db.execute("SELECT content FROM chunks WHERE id = %s", (chunk,)).fetchone()[0]
    assert content.startswith("Hàm số bậc nhất có dạng")
    assert db.execute("SELECT embedding = %s::vector FROM chunks WHERE id = %s",
                      (str(fake_vector(content)), chunk)).fetchone()[0]


async def test_remove_noise_and_figures_only_via_review(api, draft, db):
    noise = draft["add"](1, "TOÁN 8 - TẬP MỘT - trang 2", page=2)
    assert (await api.delete(f"/curation/chunks/{noise}", headers=TEACHER)).status_code == 204
    assert db.execute("SELECT count(*) FROM chunks WHERE id = %s", (noise,)).fetchone()[0] == 0
    figure = draft["chunks"]["figure"]
    assert (await api.delete(f"/curation/chunks/{figure}", headers=TEACHER)).status_code == 409


async def test_students_cannot_curate(api, draft):
    r = await api.post(doc_url(draft, "/publish"), headers=as_user("minh8a"))
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
    from tests.test_documents_api import upload

    doc = (await upload(api, pdfs.plain_pdf(1), "colan")).json()["id"]
    db.execute("UPDATE documents SET status = 'ready' WHERE id = %s", (doc,))
    assert doc not in {d["id"] for d in (await api.get("/documents", headers=as_user("minh8a"))).json()}
    await api.post(f"/curation/documents/{doc}/publish", headers=TEACHER)
    assert doc in {d["id"] for d in (await api.get("/documents", headers=as_user("minh8a"))).json()}


async def test_rejected_figure_listed_without_part_number(api, draft):
    await api.post(f"/teacher/figures/{draft['chunks']['figure']}/review", json={"action": "reject"}, headers=TEACHER)
    parts = (await api.get(doc_url(draft), headers=TEACHER)).json()["lessons"][1]["parts"]
    assert [(p["kind"], p["number"], p["review"]) for p in parts] == [("text", 1, None), ("figure", None, "rejected")]
