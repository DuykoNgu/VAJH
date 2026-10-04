import uuid

import pytest

from app.agents.base import Evidence
from app.storage import cache, relational
from app.teaching import get_part, group_parts, lesson_parts, set_part, split_ideas


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
