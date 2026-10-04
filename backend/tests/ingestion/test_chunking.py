from app.ingestion.chunking import chunk_document, embedding_text, paragraphs
from app.ingestion.lessons import LessonRange

LESSONS = [LessonRange("Bài 1", 2, 4), LessonRange("Bài 2", 5, 7)]


def sentences(page, n, length=60):
    return " ".join(f"Trang {page} câu {i} " + "x" * (length - 20) + "." for i in range(n))


def test_chunk_never_crosses_a_lesson_boundary():
    texts = [sentences(p, 3) for p in range(1, 8)]
    chunks = chunk_document(texts, LESSONS, max_chars=1500, overlap=200)
    for c in chunks:
        if c.lesson is not None:
            lesson = LESSONS[c.lesson]
            pages = {int(w.split()[0]) for w in c.content.split("Trang")[1:] if w.strip()}
            assert pages <= set(range(lesson.page_start, lesson.page_end + 1)), c
    assert not any("Trang 4" in c.content and "Trang 5" in c.content for c in chunks)


def test_text_outside_lessons_has_no_lesson():
    chunks = chunk_document([sentences(p, 2) for p in range(1, 8)], LESSONS, 1500, 200)
    assert chunks[0].lesson is None and chunks[0].page == 1 and "Trang 1" in chunks[0].content
    assert {c.lesson for c in chunks[1:]} == {0, 1}


def test_size_limit_overlap_and_start_page():
    texts = ["\n\n".join(sentences(p, 1, 300) for _ in range(4)) for p in range(1, 4)]
    chunks = chunk_document(texts, [LessonRange("A", 1, 3)], max_chars=700, overlap=320)
    assert len(chunks) > 3
    assert all(len(c.content) <= 700 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        shared = nxt.content.split(". ")[0]
        assert shared in prev.content  # câu đầu đoạn sau gối từ đoạn trước
        assert len(shared) <= 320
    assert chunks[0].page == 1 and chunks[-1].page == 3


def test_long_paragraph_split_at_sentences():
    long = " ".join(f"Câu số {i} nói về hàm số bậc nhất." for i in range(100))
    chunks = chunk_document([long], [LessonRange("A", 1, 1)], max_chars=300, overlap=0)
    assert all(len(c.content) <= 300 and c.content.endswith(".") for c in chunks)
    assert " ".join(c.content for c in chunks) == long


def test_paragraph_lines_are_joined_and_blank_pages_skipped():
    assert paragraphs("Dòng một\ncủa đoạn.\n\nĐoạn hai.") == ["Dòng một của đoạn.", "Đoạn hai."]
    assert chunk_document(["", "  \n "], [LessonRange("A", 1, 2)], 1500, 200) == []


def test_embedding_text_prefixes_lesson_title():
    assert embedding_text("Nội dung", "Bài 1. Hàm số") == "Bài 1. Hàm số\nNội dung"
    assert embedding_text("Nội dung", None) == "Nội dung"
