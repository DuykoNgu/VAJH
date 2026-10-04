"""Cắt chữ của từng bài thành đoạn (chunk) theo ranh giới đoạn văn, có phần gối đầu, không bao giờ vượt ranh giới bài."""
import re
from dataclasses import dataclass
from itertools import groupby

from app.ingestion.lessons import LessonRange

SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+")


@dataclass(frozen=True)
class TextChunk:
    lesson: int | None   # chỉ số trong danh sách bài học; None = ngoài mọi bài (bìa, mục lục, phụ lục)
    page: int            # trang bắt đầu của đoạn
    content: str


def paragraphs(text: str) -> list[str]:
    """Đoạn văn = khối cách nhau bởi dòng trống; các dòng trong một đoạn nối bằng dấu cách."""
    return [" ".join(block.split()) for block in re.split(r"\n\s*\n", text) if block.strip()]


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    parts, current = [], ""
    for sentence in SENTENCE_END.split(paragraph):
        while len(sentence) > max_chars:  # câu quá dài (hiếm): cắt cứng
            parts.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def _overlap(content: str, max_chars: int) -> str:
    """Các câu cuối của đoạn trước, tổng ≤ max_chars; không có ranh giới câu phù hợp thì không gối đầu."""
    tail = ""
    for sentence in reversed(SENTENCE_END.split(content)):
        candidate = f"{sentence} {tail}".strip()
        if len(candidate) > max_chars:
            break
        tail = candidate
    return "" if tail == content else tail


def _pack(items: list[tuple[int, str]], lesson: int | None, max_chars: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    page, current = 0, ""
    for item_page, paragraph in items:
        for piece in _split_long(paragraph, max_chars):
            if current and len(current) + 1 + len(piece) > max_chars:
                chunks.append(TextChunk(lesson, page, current))
                carry = _overlap(current, overlap)
                current = carry if carry and len(carry) + 1 + len(piece) <= max_chars else ""
                page = item_page
            if not current:
                page = item_page
            current = f"{current} {piece}" if current else piece
    if current:
        chunks.append(TextChunk(lesson, page, current))
    return chunks


def chunk_document(texts: list[str], lessons: list[LessonRange], max_chars: int, overlap: int) -> list[TextChunk]:
    """texts: chữ theo trang (texts[0] = trang 1). Trang ngoài mọi bài → chunk không thuộc bài nào."""
    owner = {page: i for i, lesson in enumerate(lessons) for page in range(lesson.page_start, lesson.page_end + 1)}
    chunks: list[TextChunk] = []
    # Các trang liền nhau cùng một bài (hoặc cùng nằm ngoài bài) được cắt chung; đổi bài → bắt đầu chunk mới
    for lesson, pages in groupby(range(1, len(texts) + 1), key=owner.get):
        items = [(page, para) for page in pages for para in paragraphs(texts[page - 1])]
        chunks += _pack(items, lesson, max_chars, overlap)
    return chunks


def embedding_text(chunk_content: str, lesson_title: str | None) -> str:
    """Văn bản đem đi embed: thêm tên bài để tìm kiếm theo chủ đề tốt hơn (content lưu nguyên văn)."""
    return f"{lesson_title}\n{chunk_content}" if lesson_title else chunk_content
