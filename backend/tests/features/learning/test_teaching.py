import uuid

import pytest

from app.core.rag.retrieval import Evidence
from app.core.storage import cache, relational
from app.features.learning.teaching import (
    clean_ideas,
    get_part,
    group_parts,
    lesson_parts,
    set_part,
    split_ideas,
)


def ev(i, kind="text", n=100):
    return Evidence(i, kind, i, "x" * n, "pending" if kind == "figure" else None, "Bài")


def test_each_figure_alone_and_short_text_kept_whole():
    parts = group_parts([ev(1, n=300), ev(2, "figure"), ev(3, n=100)], 450)
    assert [(p.number, p.kind, p.evidence[0].chunk_id) for p in parts] == [(1, "text", 1), (2, "figure", 2), (3, "text", 3)]


def test_long_text_split_into_small_parts_at_sentences():
    sentences = [f"Câu số {i} nói về đồ thị của hàm số bậc nhất trong bài học hôm nay của lớp tám." for i in range(14)]
    chunk = Evidence(7, "text", 4, " ".join(sentences), None, "Bài 2")
    assert len(chunk.content) > 1000
    parts = group_parts([chunk], 450)
    assert len(parts) >= 3 and all(len(p.evidence[0].content) <= 450 for p in parts)
    assert all(p.evidence[0].chunk_id == 7 and p.evidence[0].page == 4 for p in parts)   # vẫn trích dẫn đúng trang
    assert " ".join(p.evidence[0].content for p in parts) == chunk.content              # không cắt giữa câu, không mất chữ


def test_one_long_sentence_is_its_own_part():
    long = "Một câu rất dài " * 40 + "kết thúc."
    assert split_ideas(f"Ngắn. {long} Hết.", 450) == ["Ngắn.", long, "Hết."]


@pytest.fixture
async def infra(test_database):
    import os
    await relational.open_pool(test_database)
    cache.open_redis(os.environ["REDIS_URL"])
    yield
    await cache.close_redis()
    await relational.close_pool()


async def test_lesson_parts_skip_rejected_figures(infra, textbook):
    textbook["add"](2, "Hình bị từ chối", kind="figure", review="rejected", page=6)
    parts = await lesson_parts(textbook["lessons"][2])
    assert [(p.kind, p.evidence[0].page) for p in parts] == [("text", 4), ("figure", 5)]


async def test_part_position_per_session(infra):
    sid = uuid.uuid4()
    assert await get_part(sid) == 0
    await set_part(sid, 2)
    assert await get_part(sid) == 2


BAI1 = "Bài 1. Đơn thức"


def page(i, content, kind="text", page_no=None):
    return Evidence(i, kind, page_no or 6 + i, content, "approved" if kind == "figure" else None, BAI1)


def test_noise_is_filtered_when_the_lesson_has_no_outline():
    chunks = [
        page(1, "Chương I ĐA THỨC Ở lớp 7, các em đã học về đa thức một biến. Bài 1 ĐƠN THỨC Khái niệm, thuật ngữ "
                "• Đơn thức • Hệ số. 1 ĐƠN THỨC VÀ ĐƠN THỨC THU GỌN Khái niệm đơn thức HĐ1 Biểu thức x^2 - 2x có "
                "phải là đơn thức không? Vì sao?"),
        page(2, "Vì sao? Đơn thức là biểu thức đại số chỉ gồm một số hoặc một biến, hoặc tích của chúng. "
                "Luyện tập 1 Biểu thức nào là đơn thức? 3x^3y; -4."),
        page(3, "Hình của bài luyện tập.", kind="figure", page_no=8),
        page(4, "Muốn cộng hai đơn thức đồng dạng, ta cộng các hệ số và giữ nguyên phần biến. BÀI TẬP 1.1. Tính 2x + 3x."),
    ]
    ideas = clean_ideas(chunks, BAI1)
    text = " ".join(e.content for e in ideas)
    for noise in ("Chương", "lớp 7", "Khái niệm, thuật ngữ", "HĐ1", "Vì sao?", "Luyện tập", "1.1.", "Tính 2x"):
        assert noise not in text, noise
    assert "Khái niệm đơn thức Đơn thức là biểu thức đại số" in text            # tiêu đề dính vào định nghĩa
    assert "Muốn cộng hai đơn thức đồng dạng" in text
    assert [e.kind for e in ideas] == ["text"] and ideas[0].chunk_id == 1     # hình trong bài tập bị bỏ


def test_overlap_between_chunks_is_not_taught_twice():
    shared = "Số 0 cũng được coi là một đơn thức và nó không có bậc."
    ideas = clean_ideas([page(1, f"Bậc là tổng số mũ của các biến. {shared}"),
                         page(2, f"{shared} Hai đơn thức đồng dạng có cùng phần biến.")], BAI1)
    assert " ".join(e.content for e in ideas).count(shared) == 1


def test_lesson_without_heading_keeps_everything_that_is_not_an_exercise():
    ideas = clean_ideas([page(1, "Hàm số bậc nhất là hàm số y = ax + b với a khác 0.")], "Bài 9. Hàm số")
    assert ideas[0].content == "Hàm số bậc nhất là hàm số y = ax + b với a khác 0."
