import pytest

from app.core.ai.fakes import FakeEmbeddings
from app.core.rag.retrieval import search_knowledge
from tests.conftest import GRAPH_DESCRIPTION, as_user, running_app


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


def class_with(db, teacher, *students, name="8A"):
    cid = db.execute("INSERT INTO classes (teacher_id, name) VALUES (%s, %s) RETURNING id", (teacher, name)).fetchone()[0]
    for s in students:
        db.execute("INSERT INTO class_students VALUES (%s, %s)", (cid, s))
    return cid


def quiz_result(db, student, lesson, *answers):
    """answers: (focus, score)"""
    qz = db.execute("INSERT INTO quizzes (student_id, lesson_id) VALUES (%s, %s) RETURNING id", (student, lesson)).fetchone()[0]
    for pos, (focus, score) in enumerate(answers, 1):
        q = db.execute("INSERT INTO questions (quiz_id, position, prompt, focus, correct_answer, explanation)"
                       " VALUES (%s, %s, 'q', %s, 'a', 'e') RETURNING id", (qz, pos, focus)).fetchone()[0]
        db.execute("INSERT INTO answers (question_id, answer_text, score, feedback) VALUES (%s, 'a', %s, 'f')", (q, score))


async def test_weak_figure_understanding(api, db, make_student, make_teacher, textbook):
    teacher = make_teacher("colan")
    minh = make_student("minh8a")
    other = make_teacher("cothu", full_name="Cô Thu")
    class_with(db, teacher, minh)
    class_with(db, other, make_student("an8b", full_name="Em An"), name="8B")
    quiz_result(db, minh, textbook["lessons"][2], ("concept", 1), ("figure", 0))
    body = (await api.get("/teacher/overview", headers=as_user("colan"))).json()
    assert [c["name"] for c in body] == ["8A"]                               # chỉ lớp của mình
    (student,) = body[0]["students"]
    (lesson,) = student["lessons"]
    assert student["username"] == "minh8a" and lesson["title"] == "Bài 2. Đồ thị của hàm số bậc nhất"
    assert (lesson["concept_mastery"], lesson["figure_mastery"], lesson["weak"], lesson["weak_in"]) == \
        (1.0, 0.0, True, ["figure"])


async def test_pending_queue_and_approve_with_edit(api, db, make_teacher, textbook):
    teacher = make_teacher("colan")
    fid = textbook["chunks"]["figure"]
    queue = (await api.get("/teacher/figures", headers=as_user("colan"))).json()
    assert [(f["id"], f["page"], f["description"], f["image_url"]) for f in queue] == \
        [(fid, 5, GRAPH_DESCRIPTION, f"/figures/{fid}/image")]
    before = db.execute("SELECT embedding::text FROM chunks WHERE id = %s", (fid,)).fetchone()[0]
    edited = "Đồ thị là đường thẳng đi lên từ trái sang phải, cắt trục tung tại điểm có tung độ bằng một."
    r = await api.post(f"/teacher/figures/{fid}/review", json={"action": "approve", "description": edited},
                       headers=as_user("colan"))
    assert r.status_code == 200 and r.json()["review"] == "approved" and r.json()["description"] == edited
    content, review, by, at, after = db.execute(
        "SELECT content, review, reviewed_by, reviewed_at, embedding::text FROM chunks WHERE id = %s", (fid,)).fetchone()
    assert (content, review, by) == (edited, "approved", teacher) and at is not None and after != before
    assert (await api.get("/teacher/figures", headers=as_user("colan"))).json() == []   # rời hàng chờ
    found = await search_knowledge(FakeEmbeddings(), edited, lesson_id=textbook["lessons"][2])
    assert found[0].chunk_id == fid and not found[0].unreviewed                     # câu trả lời sau không còn cảnh báo


async def test_reject_removes_from_retrieval(api, make_teacher, textbook):
    make_teacher("colan")
    fid = textbook["chunks"]["figure"]
    r = await api.post(f"/teacher/figures/{fid}/review", json={"action": "reject"}, headers=as_user("colan"))
    assert r.json()["review"] == "rejected"
    found = await search_knowledge(FakeEmbeddings(), GRAPH_DESCRIPTION, lesson_id=textbook["lessons"][2], k=10)
    assert fid not in {e.chunk_id for e in found}
    rejected = (await api.get("/teacher/figures?status=rejected", headers=as_user("colan"))).json()
    assert [f["id"] for f in rejected] == [fid]


async def test_review_unknown_or_text_chunk_is_404(api, make_teacher, textbook):
    make_teacher("colan")
    for cid in (textbook["chunks"]["concept"], 999999):
        r = await api.post(f"/teacher/figures/{cid}/review", json={"action": "approve"}, headers=as_user("colan"))
        assert r.status_code == 404
