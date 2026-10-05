"""Một lượt hỏi đi qua Orchestrator → Knowledge → (Vision) → Tutor; LLM giả theo kịch bản, DB thật."""
import pytest

from app.agents.tutor import NOT_FOUND
from app.learning import DISCLAIMER
from tests.conftest import as_user, running_app

FIGURE_ROUTE = {"intent": "figure", "query": "Giải thích đồ thị y = 2x + 1"}
EXPLAIN_ROUTE = {"intent": "explain", "query": "Hàm số bậc nhất là gì?"}
ANSWER = "Đây là đồ thị một đường thẳng đi lên. Em thử thay x bằng không xem y bằng bao nhiêu nhé?"


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


TEACH = {"explanation": "Đồ thị hàm số bậc nhất là một đường thẳng.", "check_question": "Đồ thị là đường gì?",
         "expected_answer": "một đường thẳng"}


async def session(api, lesson_id, db=None):
    """Vào bài (LUSIA giảng phần 1 và đặt câu hỏi kiểm tra). Có `db` → coi như câu hỏi đó đã được trả lời."""
    api.app.state.llm.script(TEACH)
    r = await api.post("/sessions", json={"lesson_id": str(lesson_id)}, headers=as_user("minh8a"))
    assert r.status_code == 201, r.text
    if db is not None:
        db.execute("INSERT INTO answers (question_id, answer_text, score, feedback) SELECT q.id, 'x', 1, 'f'"
                   " FROM questions q JOIN quizzes z ON z.id = q.quiz_id WHERE z.session_id = %s"
                   " AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.question_id = q.id)", (r.json()["id"],))
    return r.json()["id"]


async def ask(api, sid, text, *script):
    api.app.state.llm.script(*script)
    r = await api.post(f"/sessions/{sid}/turns", json={"text": text}, headers=as_user("minh8a"))
    assert r.status_code == 200, r.text
    return r.json()


async def test_start_and_ask(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][2], db)
    body = await ask(api, sid, "Giải thích đồ thị trong bài này", FIGURE_ROUTE, {"answer": ANSWER, "cited": [1]})
    assert body["answer"].endswith(ANSWER)
    roles = db.execute("SELECT role, agent FROM messages WHERE session_id = %s ORDER BY id", (sid,)).fetchall()
    assert roles[-2:] == [("student", None), ("assistant", "tutor")]


async def test_figure_question_uses_vision_with_disclaimer_once(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][2], db)
    reply = await ask(api, sid, "Giải thích giúp mình đồ thị y = 2x + 1", FIGURE_ROUTE,
                      {"answer": f"{DISCLAIMER} {ANSWER}", "cited": [1]})  # model tự chèn câu cảnh báo
    assert [s["agent"] for s in reply["trace"]] == ["orchestrator", "knowledge", "vision", "tutor"]
    assert {"chunk_id": textbook["chunks"]["figure"], "page": 5, "kind": "figure"} in reply["citations"]
    assert reply["answer"].count(DISCLAIMER) == 1 and reply["answer"].startswith(DISCLAIMER)
    assert reply["sentences"][0] == DISCLAIMER


async def test_approved_figure_has_no_disclaimer(api, make_student, textbook, db):
    make_student("minh8a")
    db.execute("UPDATE chunks SET review = 'approved', reviewed_at = now() WHERE id = %s",
               (textbook["chunks"]["figure"],))
    sid = await session(api, textbook["lessons"][2], db)
    reply = await ask(api, sid, "Giải thích đồ thị", FIGURE_ROUTE, {"answer": ANSWER, "cited": [1]})
    assert "vision" in [s["agent"] for s in reply["trace"]] and DISCLAIMER not in reply["answer"]


async def test_concept_question_skips_vision(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][1], db)
    reply = await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE,
                      {"answer": "Hàm số bậc nhất có dạng y bằng a x cộng b. Theo em a có thể bằng không không?",
                       "cited": [1]})
    assert [s["agent"] for s in reply["trace"]] == ["orchestrator", "knowledge", "tutor"]
    assert reply["citations"] == [{"chunk_id": textbook["chunks"]["concept"], "page": 2, "kind": "text"}]


async def test_follow_up_uses_history(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][2], db)
    await ask(api, sid, "Giải thích đồ thị y = 2x + 1", FIGURE_ROUTE, {"answer": ANSWER, "cited": [1]})
    llm = api.app.state.llm
    llm.calls.clear()
    await ask(api, sid, "Vì sao nó cắt trục tung ở 1?",
              {"intent": "explain", "query": "Vì sao đồ thị y = 2x + 1 cắt trục tung tại 1?"},
              {"answer": "Khi x bằng không thì y bằng một. Em thử tính lại xem?", "cited": [1]})
    router, tutor = llm.calls
    for call in (router, tutor):
        contents = [m["content"] for m in call["messages"]]
        assert "Giải thích đồ thị y = 2x + 1" in contents and any(ANSWER in c for c in contents)
    assert "cắt trục tung tại 1" in tutor["messages"][-1]["content"] or "Vì sao nó" in tutor["messages"][-1]["content"]


async def test_out_of_textbook(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][1], db)
    reply = await ask(api, sid, "Đội nào thắng trận bóng tối qua?", {"intent": "other", "query": "trận bóng đá"},
                      {"answer": NOT_FOUND, "cited": []})
    assert reply["answer"] == NOT_FOUND and reply["citations"] == []
    assert reply["trace"][-1] == {"agent": "tutor", "summary": "không tìm thấy trong SGK"}


async def test_unknown_and_ended_sessions(api, make_student, textbook, db):
    make_student("minh8a")
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await api.post(f"/sessions/{missing}/turns", json={"text": "x"})).status_code == 404
    sid = await session(api, textbook["lessons"][1], db)
    assert (await api.post(f"/sessions/{sid}/end")).status_code == 204
    assert (await api.post(f"/sessions/{sid}/turns", json={"text": "x"})).status_code == 409
    assert (await api.post("/sessions", json={"lesson_id": missing})).status_code == 404


async def test_citation_numbers_never_reach_the_spoken_answer(api, make_student, textbook, db):
    make_student("minh8a")
    sid = await session(api, textbook["lessons"][1], db)
    reply = await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE,
                      {"answer": "Hàm số bậc nhất có dạng y = ax + b. [1] Em thử lấy ví dụ nhé? [1, 2]", "cited": [1]})
    assert "[" not in reply["answer"] and all("[" not in s for s in reply["sentences"])
    assert reply["citations"]                                                   # trích dẫn vẫn giữ riêng


@pytest.mark.parametrize("text, intent", [("tiếp", "next"), ("Tiếp nhé!", "next"), ("ý tiếp theo ạ", "next"),
                                          ("Kiểm tra mình đi ạ", "quiz"), ("Tiếp theo là gì vậy?", None),
                                          ("Đơn thức là gì?", None)])
def test_quick_intents_skip_the_llm(text, intent):
    from app.agents.orchestrator import quick_intent

    assert quick_intent(text) == intent
