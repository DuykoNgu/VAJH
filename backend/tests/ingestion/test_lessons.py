import pytest

from app.ai.fakes import FakeLLM
from app.config import get_settings
from app.ingestion.lessons import LessonRange, LessonRangeError, segment, validate_ranges
from app.ingestion.pdf import bookmarks, open_pdf, page_texts
from tests import pdfs


async def run(data, llm=None, title="Tài liệu"):
    llm = llm or FakeLLM(get_settings())
    with open_pdf(data, 400) as doc:
        texts = [p.text for p in page_texts(doc)]
        return await segment(llm, title, texts, bookmarks(doc)), llm


async def test_bookmarked_textbook():
    (lessons, source), llm = await run(pdfs.lessons_pdf())
    assert source == "bookmarks" and llm.calls == []
    assert [(l.page_start, l.page_end) for l in lessons] == [(2, 4), (5, 7)]
    assert lessons[1].title == "Bài 2. Đồ thị của hàm số bậc nhất"


async def test_toc_with_offset_pages():
    llm = FakeLLM(get_settings()).script({"entries": [
        {"title": "Bài 1. Hàm số bậc nhất", "printed_page": 1},
        {"title": "Bài 2. Đồ thị của hàm số bậc nhất", "printed_page": 3}]})
    (lessons, source), _ = await run(pdfs.toc_pdf(), llm)
    assert source == "toc"
    assert [(l.title, l.page_start, l.page_end) for l in lessons] == [
        ("Bài 1. Hàm số bậc nhất", 3, 4), ("Bài 2. Đồ thị của hàm số bậc nhất", 5, 6)]
    assert llm.calls[0]["route"] == "toc"


async def test_unverifiable_toc_falls_back_to_single_lesson():
    llm = FakeLLM(get_settings()).script({"entries": [
        {"title": "Chương không có thật", "printed_page": 1}, {"title": "Bài ma", "printed_page": 2}]})
    (lessons, source), _ = await run(pdfs.toc_pdf(), llm, title="Toán 8")
    assert source == "single" and lessons == [LessonRange("Toán 8", 1, 6)]


async def test_no_structure_single_lesson():
    llm = FakeLLM(get_settings()).script({"entries": []})
    (lessons, source), _ = await run(pdfs.plain_pdf(3), llm, title="Phiếu học tập")
    assert source == "single" and lessons == [LessonRange("Phiếu học tập", 1, 3)]


@pytest.mark.parametrize("ranges, message", [
    ([("A", 0, 2)], "outside"),
    ([("A", 1, 9)], "outside"),
    ([("A", 3, 2)], "start after end"),
    ([("A", 1, 3), ("B", 3, 5)], "overlaps"),
    ([("A", 4, 5), ("B", 1, 2)], "overlaps or is out of order"),
    ([(" ", 1, 2)], "no title"),
])
def test_invalid_ranges(ranges, message):
    with pytest.raises(LessonRangeError, match=message):
        validate_ranges([LessonRange(*r) for r in ranges], page_count=7)


def test_valid_ranges_with_gaps():
    validate_ranges([LessonRange("A", 2, 4), LessonRange("B", 6, 7)], page_count=7)


async def test_malformed_toc_output_falls_back_to_single_lesson():
    llm = FakeLLM(get_settings())  # không có kịch bản → trả chữ thay vì JSON mục lục
    (lessons, source), _ = await run(pdfs.plain_pdf(2), llm, title="Phiếu")
    assert source == "single" and lessons == [LessonRange("Phiếu", 1, 2)]


def test_lesson_heading_after_chapter_intro_is_verified():
    from app.ingestion.lessons import TocEntry, verify_toc

    intro = "Chương I. Đa thức. " + "Ở lớp 7 các em đã học về đa thức một biến. " * 8   # ~350 ký tự giới thiệu chương
    texts = ["Mục lục", intro + "Bài 1. Đơn thức. Khái niệm...", "Luyện tập chung. Ví dụ 1..."]
    entries = [TocEntry(title="Bài 1. Đơn thức", printed_page=1), TocEntry(title="Luyện tập chung", printed_page=2)]
    assert len(intro) > 300
    assert verify_toc(entries, texts) == [("Bài 1. Đơn thức", 2), ("Luyện tập chung", 3)]
