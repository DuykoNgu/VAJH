"""Dàn ý giảng: rút ý chính bằng LLM, kiểm tra kết quả, lưu / thay thế, lỗi thì giữ dàn ý cũ."""
import pytest

from app.config import get_settings
from app.core.ai.fakes import FakeLLM
from app.core.ai.llm import Refusal
from app.features.documents.outline import (
    Outline,
    OutlineError,
    generate_outline,
    load_outline,
    outline_document,
    passages,
    strip_overlap,
    to_points,
)
from tests.conftest import running_app


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


def draft(text_id, figure_id, foreign=999):
    return {"opening": "Bạn An đi bộ 2 km mỗi giờ; sau x giờ An đi được bao xa?", "opening_sources": [text_id],
            "points": [
                {"title": "Đồ thị là đường thẳng", "content": "Đồ thị của y = ax + b là một đường thẳng.",
                 "question": "Đồ thị của y = 2x + 1 là đường gì?", "answer": "một đường thẳng",
                 "sources": [text_id, foreign]},
                {"title": "", "content": "ý rỗng bị bỏ", "question": "", "answer": "", "sources": []},
                {"title": "Giao điểm với trục tung", "content": "Đường thẳng cắt trục tung tại tung độ b.",
                 "question": "Cắt trục tung ở đâu?", "answer": "", "sources": [figure_id]}]}


def test_strip_overlap():
    previous = "Câu một nói về đơn thức. Câu hai nói về hệ số của đơn thức."
    assert strip_overlap(previous, "Câu hai nói về hệ số của đơn thức. Câu ba nói về bậc.") == "Câu ba nói về bậc."
    assert strip_overlap("Khác hẳn.", "Câu ba.") == "Câu ba."


def test_passages_number_by_chunk_and_mark_figures():
    out = passages([(7, "text", 4, "Đồ thị là đường thẳng."), (9, "figure", 5, "Trục x nằm ngang.")])
    assert out == ["[7] (trang 4) Đồ thị là đường thẳng.", "[9] (trang 5) MÔ TẢ HÌNH: Trục x nằm ngang."]


def test_to_points_validates_the_llm_output():
    points = to_points(Outline.model_validate(draft(7, 9)), {7, 9})
    assert [(p.position, p.title) for p in points] == [(0, "Mở đầu"), (1, "Đồ thị là đường thẳng"),
                                                       (2, "Giao điểm với trục tung")]
    assert points[1].chunk_ids == (7,)                                   # nguồn ngoài bài bị bỏ
    assert (points[2].question, points[2].answer) == (None, None)       # câu hỏi thiếu đáp án → bỏ cả hai


async def test_generate_stores_and_replaces_and_keeps_old_on_failure(api, textbook):
    lesson, text_id, figure_id = textbook["lessons"][2], textbook["chunks"]["graph_text"], textbook["chunks"]["figure"]
    llm = FakeLLM(get_settings()).script(draft(text_id, figure_id))
    await generate_outline(llm, lesson)
    prompt = llm.calls[0]["messages"][0]["content"]
    assert llm.calls[0]["route"] == "outline" and f"[{figure_id}] (trang 5) MÔ TẢ HÌNH" in prompt
    stored = await load_outline(lesson)
    assert [(p.position, p.title, p.chunk_ids) for p in stored] == [
        (0, "Mở đầu", (text_id,)), (1, "Đồ thị là đường thẳng", (text_id,)), (2, "Giao điểm với trục tung", (figure_id,))]
    llm.script(Refusal("other"))
    with pytest.raises(OutlineError):
        await generate_outline(llm, lesson)
    assert await load_outline(lesson) == stored                          # lỗi: giữ dàn ý cũ


async def test_outline_document_reports_each_lesson(api, textbook):
    llm = FakeLLM(get_settings()).script(Refusal("other"),
                                         draft(textbook["chunks"]["graph_text"], textbook["chunks"]["figure"]))
    result = await outline_document(llm, textbook["document"], limit=1)
    assert result == [("Bài 1. Hàm số bậc nhất", 0), ("Bài 2. Đồ thị của hàm số bậc nhất", 2)]
