import uuid

"""Giảng bài theo từng phần: vào bài → phần 1 → câu hỏi kiểm tra → chấm → "tiếp" → phần hình (Vision) → tóm tắt."""
import pytest

from app.features.learning.hooks import HOOKS
from app.features.learning.service import DISCLAIMER, NEXT_PART, OFFER_QUIZ, TO_SUMMARY
from tests.conftest import as_user, running_app
from tests.features.learning.test_learning import ask

TEACH_1 = {"explanation": "Đồ thị của hàm số y bằng a x cộng b là một đường thẳng.",
           "check_question": "Đồ thị của hàm số bậc nhất là đường gì?", "expected_answer": "một đường thẳng"}
TEACH_2 = {"explanation": "Hình vẽ cho thấy đường thẳng đi lên, cắt trục tung tại điểm một.",
           "check_question": "Đường thẳng cắt trục tung tại điểm nào?", "expected_answer": "tại điểm có tung độ bằng một"}
NEXT = {"intent": "next", "query": "tiếp"}


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


def pending(db, sid):
    return db.execute("SELECT q.prompt, q.focus, q.choices FROM questions q JOIN quizzes z ON z.id = q.quiz_id"
                      " WHERE z.session_id = %s AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.question_id = q.id)",
                      (sid,)).fetchall()


async def enter(api, lesson_id):
    api.app.state.llm.script(TEACH_1)
    r = await api.post("/sessions", json={"lesson_id": str(lesson_id)}, headers=as_user("minh5a"))
    assert r.status_code == 201, r.text
    return r.json()


async def test_entering_a_lesson_teaches_part_1(api, make_student, textbook, db):
    make_student("minh5a")
    body = await enter(api, textbook["lessons"][2])
    assert body["mode"] == "teach" and "Bài có 2 phần." in body["answer"] and "Phần 1." in body["answer"]
    assert body["answer"].endswith(TEACH_1["check_question"])
    assert [t["agent"] for t in body["trace"]] == ["tutor", "assessment"]
    assert pending(db, body["id"]) == [(TEACH_1["check_question"], "concept", None)]
    assert api.app.state.llm.calls[0]["route"] == "tutor" and "ĐI THẲNG VÀO KIẾN THỨC" in api.app.state.llm.calls[0]["system"]


async def test_correct_answer_then_figure_part_with_vision(api, make_student, textbook, db):
    make_student("minh5a")
    sid = (await enter(api, textbook["lessons"][2]))["id"]
    r = await ask(api, sid, "một đường thẳng", {"is_student_question": False, "score": 1, "feedback": "Giỏi lắm.",
                                                "re_explanation": ""})
    assert r["answer"] == f"Đúng rồi! Giỏi lắm. {NEXT_PART}" and r["mode"] == "teach"
    assert db.execute("SELECT score FROM answers").fetchone()[0] == 1
    r = await ask(api, sid, "tiếp", TEACH_2)
    assert [t["agent"] for t in r["trace"]] == ["orchestrator", "vision", "tutor", "assessment"]
    assert r["answer"].startswith(f"Phần 2. {DISCLAIMER}") and r["answer"].endswith(TEACH_2["check_question"])
    assert pending(db, sid) == [(TEACH_2["check_question"], "figure", None)]


async def test_wrong_answer_re_explains(api, make_student, textbook, db):
    make_student("minh5a")
    sid = (await enter(api, textbook["lessons"][2]))["id"]
    r = await ask(api, sid, "đường cong", {"is_student_question": False, "score": 0, "feedback": "Không sao.",
                                           "re_explanation": "Đồ thị hàm số bậc nhất luôn là đường thẳng."})
    assert r["answer"] == f"Chưa đúng. Không sao. Đồ thị hàm số bậc nhất luôn là đường thẳng. {NEXT_PART}"
    assert db.execute("SELECT score FROM answers").fetchone()[0] == 0


async def test_student_interrupts_with_a_question(api, make_student, textbook, db):
    make_student("minh5a")
    sid = (await enter(api, textbook["lessons"][2]))["id"]
    r = await ask(api, sid, "Trục tung là trục nào?",
                  {"is_student_question": True, "score": 0, "feedback": "", "re_explanation": ""},
                  {"intent": "explain", "query": "Trục tung là trục nào?"},
                  {"answer": "Trục tung là trục thẳng đứng. Em thử nói xem trục hoành là trục nào?", "cited": [1]})
    # Bài 2 có hình trong kết quả tìm kiếm → Vision tham gia và Tutor trích dẫn hình chưa duyệt → có câu cảnh báo
    assert r["answer"] == (f"{DISCLAIMER} Trục tung là trục thẳng đứng. "
                           f"Quay lại câu hỏi lúc nãy nhé: {TEACH_1['check_question']}")
    assert [t["agent"] for t in r["trace"]][:2] == ["assessment", "orchestrator"]
    assert db.execute("SELECT count(*) FROM answers").fetchone()[0] == 0          # chưa lưu câu trả lời nào
    assert pending(db, sid) == [(TEACH_1["check_question"], "concept", None)]


async def test_end_of_lesson_summary_offers_quiz_and_mastery_counts_checks(api, make_student, textbook, db):
    student = make_student("minh5a")
    sid = (await enter(api, textbook["lessons"][2]))["id"]
    grade = {"is_student_question": False, "score": 1, "feedback": "Tốt.", "re_explanation": ""}
    await ask(api, sid, "một đường thẳng", grade)
    await ask(api, sid, "tiếp", TEACH_2)
    r = await ask(api, sid, "điểm một", {**grade, "score": 0.5, "re_explanation": "Là điểm có tung độ bằng một."})
    assert r["answer"].startswith("Em trả lời đúng một phần.") and r["answer"].endswith(TO_SUMMARY)
    r = await ask(api, sid, "tiếp", {"answer": "Đồ thị hàm số bậc nhất là đường thẳng.", "cited": [1]})
    assert r["answer"].startswith("Mình đã học hết bài.") and r["answer"].endswith(OFFER_QUIZ)
    concept, figure = db.execute("SELECT concept_mastery, figure_mastery FROM lesson_mastery WHERE student_id = %s",
                                 (student,)).fetchone()
    assert (float(concept), float(figure)) == (1.0, 0.5)


async def test_lesson_without_content(api, make_student, db):
    make_student("minh5a")
    doc = db.execute("INSERT INTO documents (kind, title, subject, grade, storage_key, status, published_at) VALUES"
                     " ('textbook', 'Rỗng', 'toan', 8, 'sgk/r.pdf', 'ready', now()) RETURNING id").fetchone()[0]
    lesson = db.execute("INSERT INTO lessons (document_id, position, title, page_start, page_end)"
                        " VALUES (%s, 1, 'Bài trống', 1, 1) RETURNING id", (doc,)).fetchone()[0]
    r = await api.post("/sessions", json={"lesson_id": str(lesson)}, headers=as_user("minh5a"))
    assert "chưa có nội dung" in r.json()["answer"] and r.json()["mode"] == "chat"


def test_drop_trailing_question_keeps_single_question():
    from app.features.learning.service import drop_trailing_question

    assert drop_trailing_question("Trục tung là trục dọc. Em thử nói xem?") == "Trục tung là trục dọc."
    assert drop_trailing_question("Chỉ một câu hỏi?") == "Chỉ một câu hỏi?"
    assert drop_trailing_question("Không có câu hỏi. Hết.") == "Không có câu hỏi. Hết."


async def test_hook_before_part_1_with_bank_suggestions(api, make_student, textbook):
    make_student("minh5a")
    hook = "Em hãy tưởng tượng mình đứng giữa một ngã tư, hai con đường vuông góc dưới chân."
    api.app.state.llm.script({**TEACH_1, "hook": hook})
    r = await api.post("/sessions", json={"lesson_id": str(textbook["lessons"][2])}, headers=as_user("minh5a"))
    assert f"Bài có 2 phần. {hook} Phần 1. {TEACH_1['explanation']}" in r.json()["answer"]
    task = api.app.state.llm.calls[-1]["messages"][-1]["content"]
    descartes = next(h for h in HOOKS if h.id == "descartes")
    assert "MỞ ĐẦU" in task and descartes.spoken in task                      # gợi ý đúng chủ đề đồ thị


async def test_invented_quotes_not_given_real_authors(api, make_student, textbook):
    make_student("minh5a")
    await enter(api, textbook["lessons"][2])
    task = api.app.state.llm.calls[-1]["messages"][-1]["content"]
    assert "KHÔNG gán cho người thật có tên" in task


async def test_later_parts_have_no_hook(api, make_student, textbook, db):
    make_student("minh5a")
    sid = (await enter(api, textbook["lessons"][2]))["id"]
    await ask(api, sid, "một đường thẳng", {"is_student_question": False, "score": 1, "feedback": "Tốt.",
                                            "re_explanation": ""})
    r = await ask(api, sid, "tiếp", {**TEACH_2, "hook": "Câu dẫn không được dùng ở phần 2."})
    assert "Câu dẫn không được dùng" not in r["answer"] and r["answer"].startswith("Phần 2.")
    assert "MỞ ĐẦU" not in api.app.state.llm.calls[-1]["messages"][-1]["content"]


def outline(db, lesson, opening, points):
    """points: (title, content, question, answer, chunk_ids)"""
    db.execute("INSERT INTO lesson_points (lesson_id, position, title, content, chunk_ids) VALUES (%s, 0, 'Mở đầu', %s,"
               " '{}')", (lesson, opening))
    for position, (title, content, question, answer, ids) in enumerate(points, 1):
        db.execute("INSERT INTO lesson_points (lesson_id, position, title, content, question, answer, chunk_ids)"
                   " VALUES (%s, %s, %s, %s, %s, %s, %s)", (lesson, position, title, content, question, answer, ids))


RIGHT = {"is_student_question": False, "score": 1, "feedback": "Tốt.", "re_explanation": ""}


async def test_outline_lesson_goes_straight_to_the_points(api, make_student, textbook, db):
    make_student("minh5a")
    lesson, text_id, figure_id = textbook["lessons"][2], textbook["chunks"]["graph_text"], textbook["chunks"]["figure"]
    outline(db, lesson, "Bạn An đi bộ 2 km mỗi giờ; sau x giờ An đi được bao xa?", [
        ("Đồ thị là đường thẳng", "Đồ thị của y = ax + b là một đường thẳng.", "Đồ thị của y = 2x + 1 là đường gì?",
         "một đường thẳng", [text_id]),
        ("Giao điểm với trục tung", "Đường thẳng cắt trục tung tại tung độ b.", "Cắt trục tung ở đâu?", "tại 1",
         [figure_id])])
    api.app.state.llm.script({**TEACH_1, "hook": "An đi 2 km mỗi giờ, sau x giờ đi được 2x km.",
                              "expected_answer": "đáp án Tutor tự nghĩ"})
    r = await api.post("/sessions", json={"lesson_id": str(lesson)}, headers=as_user("minh5a"))
    answer = r.json()["answer"]
    assert "Bài có 2 ý: một, Đồ thị là đường thẳng; hai, Giao điểm với trục tung." in answer      # lộ trình trước
    assert "An đi 2 km mỗi giờ, sau x giờ đi được 2x km. Ý 1: Đồ thị là đường thẳng." in answer
    task = api.app.state.llm.calls[-1]["messages"][-1]["content"]
    assert "«Bạn An đi bộ 2 km mỗi giờ" in task and "«Đồ thị của y = 2x + 1 là đường gì?»" in task
    assert "[1] ĐOẠN SÁCH" in task and "Đồ thị là đường thẳng. Đồ thị của y = ax + b" in task      # kiến thức của ý
    sid = r.json()["id"]
    assert pending(db, sid)[0][0] == TEACH_1["check_question"]
    assert db.execute("SELECT correct_answer FROM questions").fetchone()[0] == "một đường thẳng"  # đáp án của sách

    await ask(api, sid, "một đường thẳng", RIGHT)
    second = await ask(api, sid, "tiếp", TEACH_2)
    assert second["answer"].startswith("Ý 2: Giao điểm với trục tung.") and "vision" in [s["agent"] for s in second["trace"]]
    await ask(api, sid, "tại một", RIGHT)
    calls = len(api.app.state.llm.calls)
    done = await ask(api, sid, "tiếp")
    assert done["answer"] == ("Mình đã học hết bài. Bài có 2 ý: một, Đồ thị là đường thẳng; hai, Giao điểm với trục"
                              f" tung. {OFFER_QUIZ}")
    assert len(api.app.state.llm.calls) == calls                                       # "tiếp" + tóm tắt: không gọi LLM


async def test_without_outline_the_opening_hook_is_direct(api, make_student, textbook):
    make_student("minh5a")
    await enter(api, textbook["lessons"][1])                          # "Bài 1. Hàm số bậc nhất": không có câu đúng chủ đề
    task = api.app.state.llm.calls[-1]["messages"][-1]["content"]
    assert "nói thẳng bài này giúp em làm được gì" in task and "Gợi ý" not in task and "Có thể dùng" not in task


def test_grader_verifies_the_expected_answer_itself():
    from app.prompts.learning import OPEN_SYSTEM

    assert "chỉ để THAM KHẢO và có thể sai: tự giải lại câu hỏi" in OPEN_SYSTEM


async def test_next_part_is_prepared_while_the_student_answers(api, make_student, textbook, db, monkeypatch):
    import asyncio

    from app.config import get_settings
    from app.features.learning import service as learning

    monkeypatch.setattr(get_settings(), "prefetch_parts", True)
    make_student("minh5a")
    api.app.state.llm.script(TEACH_1, TEACH_2)                      # ý 1 khi vào bài, ý 2 được soạn sẵn ngay sau đó
    r = await api.post("/sessions", json={"lesson_id": str(textbook["lessons"][2])}, headers=as_user("minh5a"))
    sid = r.json()["id"]
    for _ in range(100):                                            # chờ việc soạn sẵn (chạy ngầm) xong
        task = learning._AHEAD.get((uuid.UUID(sid), 2))
        if task and task.done():
            break
        await asyncio.sleep(0.01)
    await ask(api, sid, "một đường thẳng", RIGHT)
    calls = len(api.app.state.llm.calls)
    second = await ask(api, sid, "tiếp")
    assert second["answer"].startswith("Phần 2.") and TEACH_2["explanation"] in second["answer"]
    assert len(api.app.state.llm.calls) == calls                     # "tiếp": không chờ LLM nào
    assert any("(soạn sẵn)" in s["summary"] for s in second["trace"])
