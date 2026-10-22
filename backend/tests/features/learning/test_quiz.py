"""Quiz bằng giọng nói qua API phiên học (LLM giả theo kịch bản, DB thật)."""
import pytest

from app.features.learning.agents.assessment import NO_LESSON
from tests.conftest import as_user, running_app
from tests.features.learning.test_learning import ask, session

QUIZ_ROUTE = {"intent": "quiz", "query": "kiểm tra"}
DRAFT = {"questions": [
    {"prompt": "Hàm số bậc nhất có dạng nào?", "choices": ["y bằng a x cộng b", "y bằng x bình phương", "y bằng một chia x"],
     "correct": "y bằng a x cộng b", "explanation": "Hàm số bậc nhất có dạng y bằng a x cộng b.", "focus": "concept"},
    {"prompt": "Đồ thị cắt trục tung tại điểm có tung độ bằng mấy?", "choices": ["0", "1", "2"], "correct": "1",
     "explanation": "Thay x bằng không thì y bằng một.", "focus": "figure"},
    {"prompt": "Hệ số a trong y bằng hai x cộng một là bao nhiêu?", "choices": ["1", "2", "3"], "correct": "2",
     "explanation": "a là số đứng trước x.", "focus": "concept"},
]}


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


async def start_quiz(api, textbook, db):
    sid = await session(api, textbook["lessons"][2], db)
    reply = await ask(api, sid, "Kiểm tra mình 3 câu nhé", QUIZ_ROUTE, DRAFT)
    return sid, reply


async def test_quiz_generated_from_the_lesson(api, make_student, textbook, db):
    student = make_student("minh5a")
    sid, reply = await start_quiz(api, textbook, db)
    assert reply["mode"] == "quiz" and [s["agent"] for s in reply["trace"]] == ["orchestrator", "assessment"]
    assert "Câu 1: Hàm số bậc nhất có dạng nào?" in reply["answer"] and "A, y bằng a x cộng b" in reply["answer"]
    rows = db.execute("SELECT z.student_id, z.lesson_id, q.focus FROM quizzes z JOIN questions q ON q.quiz_id = z.id"
                      " WHERE z.session_id = %s AND q.choices IS NOT NULL ORDER BY q.position", (sid,)).fetchall()
    assert len(rows) == 3 and {r[0] for r in rows} == {student} and "figure" in {r[2] for r in rows}
    material = api.app.state.llm.calls[-1]["messages"][0]["content"]
    assert "MÔ TẢ HÌNH" in material and "Hàm số bậc nhất là" not in material  # chỉ nội dung bài 2


async def test_quiz_without_lesson(api, make_student):
    make_student("minh5a")
    r = await api.post("/sessions", json={}, headers=as_user("minh5a"))  # không chọn bài → không giảng
    reply = await ask(api, r.json()["id"], "kiểm tra mình đi", QUIZ_ROUTE)
    assert reply["answer"] == NO_LESSON and reply["mode"] == "chat"


async def test_spoken_answers_graded_until_finished_and_mastery_split(api, make_student, textbook, db):
    student = make_student("minh5a")
    sid, _ = await start_quiz(api, textbook, db)
    api.app.state.llm.calls.clear()
    r1 = await ask(api, sid, "câu A", {"choice_index": 0, "feedback": "Em nhớ bài tốt lắm."})
    assert r1["mode"] == "quiz" and r1["answer"].startswith("Đúng rồi!") and "Câu 2:" in r1["answer"]
    assert [s["agent"] for s in r1["trace"]] == ["assessment"]          # không hỏi Orchestrator khi đang quiz
    assert all(c["route"] == "assessment" for c in api.app.state.llm.calls)
    r2 = await ask(api, sid, "không", {"choice_index": 0, "feedback": "Không sao, mình xem lại nhé."})
    assert "Chưa đúng. Đáp án đúng là B, 1." in r2["answer"] and "Câu 3:" in r2["answer"]
    r3 = await ask(api, sid, "câu B, là hai", {"choice_index": 1, "feedback": "Chính xác."})
    assert r3["mode"] == "chat" and "Em đúng 2 trên 3 câu." in r3["answer"]
    scores = db.execute("SELECT a.score FROM answers a JOIN questions q ON q.id = a.question_id"
                        " WHERE q.choices IS NOT NULL ORDER BY q.position").fetchall()
    assert [float(s[0]) for s in scores] == [1.0, 0.0, 1.0]
    mastery = db.execute("SELECT concept_mastery, figure_mastery FROM lesson_mastery WHERE student_id = %s"
                         " AND lesson_id = %s", (student, textbook["lessons"][2])).fetchone()
    assert [float(m) for m in mastery] == [1.0, 0.0]
    after = await ask(api, sid, "Hàm số là gì?", {"intent": "explain", "query": "Hàm số là gì?"},
                      {"answer": "Hàm số là quy tắc.", "cited": [1]})
    assert after["trace"][0]["agent"] == "orchestrator"                 # hết quiz → quay lại hỏi đáp


async def test_invalid_draft_retried_then_rejected(api, make_student, textbook, db):
    make_student("minh5a")
    bad = {"questions": [{"prompt": "x", "choices": ["a", "b"], "correct": "c", "explanation": "", "focus": "concept"}]}
    sid = await session(api, textbook["lessons"][2], db)
    reply = await ask(api, sid, "kiểm tra", bad, bad)  # "kiểm tra": Orchestrator nhận ra ngay, không gọi LLM
    assert reply["mode"] == "chat" and "chưa tạo được" in reply["answer"]


async def test_quiz_is_drafted_from_the_outline_when_there_is_one(api, make_student, textbook, db):
    make_student("minh5a")
    db.execute("INSERT INTO lesson_points (lesson_id, position, title, content, question, answer) VALUES"
               " (%s, 1, 'Đồ thị là đường thẳng', 'Đồ thị của y = ax + b là một đường thẳng.', 'Đường gì?', 'thẳng')",
               (textbook["lessons"][2],))
    await start_quiz(api, textbook, db)
    material = api.app.state.llm.calls[-1]["messages"][0]["content"]
    assert material.startswith("Ý: Đồ thị là đường thẳng. Đồ thị của y = ax + b") and "Luyện tập: Đường gì?" in material
    assert "MÔ TẢ HÌNH" in material
