"""Chia tài liệu thành bài học: bookmark PDF → mục lục (LLM đọc, đối chiếu với trang thật) → một bài cho cả tài liệu."""
import logging
import re
import unicodedata
from dataclasses import dataclass, replace
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.ai.llm import LLMClient, LLMResult

log = logging.getLogger("lusia.ingestion")

TOC_SCAN_PAGES = 6
TITLE_HEAD_CHARS = 600  # tiêu đề bài ở đầu trang bắt đầu bài (trang mở chương: sau đoạn giới thiệu chương)
TOC_PROMPT = (
    "Dưới đây là chữ của các trang đầu một tài liệu học tập. Nếu có MỤC LỤC, liệt kê các bài học theo thứ tự: tiêu đề "
    "đầy đủ đúng như in và số trang in bên cạnh. Lấy các bài học và các buổi ôn riêng ('Luyện tập chung', 'Bài tập "
    "cuối chương', 'Ôn tập'); bỏ tên chương và mục nhỏ bên trong bài. Không có mục lục thì trả về danh sách rỗng."
)


class LessonRangeError(ValueError):
    pass


@dataclass(frozen=True)
class LessonRange:
    title: str
    page_start: int
    page_end: int
    id: UUID | None = None


class TocEntry(BaseModel):
    title: str
    printed_page: int


class TocResult(BaseModel):
    entries: list[TocEntry]


def validate_ranges(lessons: list[LessonRange], page_count: int) -> None:
    previous_end = 0
    for i, lesson in enumerate(lessons, 1):
        if not lesson.title.strip():
            raise LessonRangeError(f"lesson {i} has no title")
        if not 1 <= lesson.page_start <= lesson.page_end <= page_count:
            raise LessonRangeError(f"lesson {i} pages {lesson.page_start}-{lesson.page_end} outside 1-{page_count}"
                                   " or start after end")
        if lesson.page_start <= previous_end:
            raise LessonRangeError(f"lesson {i} overlaps or is out of order")
        previous_end = lesson.page_end


def _ranges(starts: list[tuple[str, int]], page_count: int) -> list[LessonRange]:
    """[(title, start)] đã sắp theo trang → mỗi bài kết thúc trước bài sau; bài cuối tới hết tài liệu."""
    unique = []
    for title, start in sorted(starts, key=lambda s: s[1]):
        if not unique or start > unique[-1][1]:
            unique.append((title, start))
    return [LessonRange(title, start, (unique[i + 1][1] - 1) if i + 1 < len(unique) else page_count)
            for i, (title, start) in enumerate(unique)]


def from_bookmarks(marks: list[tuple[int, str, int]], page_count: int) -> list[LessonRange] | None:
    for level in sorted({lvl for lvl, _, _ in marks}):
        entries = [(title, page) for lvl, title, page in marks if lvl == level]
        if len(entries) >= 2:
            return _ranges(entries, page_count)
    return None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def verify_toc(entries: list[TocEntry], texts: list[str]) -> list[tuple[str, int]]:
    """Số trang in ≠ chỉ số PDF: thử các độ lệch (nhỏ trước), giữ độ lệch khớp nhiều tiêu đề nhất.

    Một mục "khớp" khi tiêu đề (đã bỏ dấu) nằm ở đầu trang PDF = số trang in + độ lệch.
    """
    heads = [normalize(t)[:TITLE_HEAD_CHARS] for t in texts]

    def page_for(entry: TocEntry, offset: int) -> int | None:
        page, title = entry.printed_page + offset, normalize(entry.title)[:60]
        return page if title and 1 <= page <= len(texts) and title in heads[page - 1] else None

    best: list[tuple[str, int]] = []
    for offset in sorted(range(-len(texts), len(texts)), key=abs):
        verified = [(e.title.strip(), page) for e in entries if (page := page_for(e, offset))]
        if len(verified) > len(best):
            best = verified
    return best


async def from_toc(llm: LLMClient, texts: list[str]) -> list[LessonRange] | None:
    scan = "\n\n".join(f"--- Trang {i} ---\n{t}" for i, t in enumerate(texts[:TOC_SCAN_PAGES], 1))
    try:
        result = await llm.complete("toc", [{"role": "user", "content": f"{TOC_PROMPT}\n\n{scan}"}],
                                    schema=TocResult)
    except ValidationError as e:  # LLM trả mục lục sai định dạng → coi như không có mục lục (lỗi mạng vẫn ném ra)
        log.warning("table of contents unreadable", extra={"error": str(e)[:300]})
        return None
    if not isinstance(result, LLMResult) or not result.parsed.entries:
        return None
    verified = verify_toc(result.parsed.entries, texts)
    return _ranges(verified, len(texts)) if len(verified) >= 2 else None


def single_lesson(title: str, page_count: int) -> list[LessonRange]:
    return [LessonRange(title, 1, page_count)]


async def segment(llm: LLMClient, title: str, texts: list[str],
                  marks: list[tuple[int, str, int]]) -> tuple[list[LessonRange], str]:
    """(bài học, nguồn: bookmarks | toc | single)."""
    page_count = len(texts)
    if (lessons := from_bookmarks(marks, page_count)) is not None:
        return lessons, "bookmarks"
    if (lessons := await from_toc(llm, texts)) is not None:
        return lessons, "toc"
    return single_lesson(title, page_count), "single"


def with_ids(lessons: list[LessonRange], ids: list[UUID]) -> list[LessonRange]:
    return [replace(lesson, id=i) for lesson, i in zip(lessons, ids, strict=True)]
