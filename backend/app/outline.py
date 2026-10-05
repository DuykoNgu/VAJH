"""Dàn ý giảng: rút các Ý CHÍNH của một bài từ nguồn tri thức (một lượt LLM / bài), lưu vào lesson_points.

LUSIA giảng theo dàn ý (nêu thẳng kiến thức, ví dụ trong sách, câu hỏi từ bài luyện tập) thay vì đọc lần lượt các đoạn
SGK thô - vốn lẫn lời giới thiệu chương, hộp mục tiêu, hoạt động, bài tập và phần gối đầu giữa các đoạn.

Tạo dàn ý cho tài liệu đã nạp:  python -m app.outline <document_id>
"""
import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from app.ai.llm import LLMClient, Refusal
from app.storage import relational

log = logging.getLogger("lusia.outline")
MAX_POINTS = 8
OUTLINE_SYSTEM = (
    "Bạn soạn DÀN Ý GIẢNG cho MỘT bài trong sách giáo khoa, để gia sư giảng bằng lời cho học sinh khiếm thị. Đầu vào "
    "là các đoạn sách đánh số [n] theo thứ tự trang (chữ do OCR, có thể lẫn nhiễu). "
    "`points`: các Ý CHÍNH của bài theo đúng thứ tự trong sách; mỗi ý là một kiến thức cốt lõi: định nghĩa, quy tắc, "
    "tính chất, công thức hoặc cách làm. Thường 3 đến 6 ý, tối đa 8. "
    "BỎ QUA, không biến thành ý: lời giới thiệu chương; hộp 'Khái niệm, thuật ngữ' và 'Kiến thức, kĩ năng' (chỉ dùng để "
    "biết bài có những ý nào); các hoạt động HĐ (chỉ lấy kết luận mà chúng dẫn tới); lời thoại nhân vật; chữ chìm, số "
    "trang, tiêu đề lặp. Bài tập ('Luyện tập', 'Vận dụng', 'Bài tập', các câu 1.1, 1.2…) KHÔNG phải ý giảng: dùng chúng "
    "để đặt câu hỏi kiểm tra cho ý tương ứng. "
    "Mỗi ý: `title` ngắn (tối đa 8 từ, ví dụ 'Đơn thức là gì'); `content` 1 đến 3 câu NÊU THẲNG kiến thức như sách "
    "viết, kèm MỘT ví dụ cụ thể lấy từ sách; `question` MỘT câu hỏi kiểm tra ngắn về đúng ý đó, trả lời được bằng vài "
    "từ (ưu tiên chuyển từ bài luyện tập trong sách; không hỏi chung chung kiểu 'có gì giống nhau'); `answer` đáp án "
    "đúng và ngắn (tự tính lại cho chắc); `sources` các số [n] đã dùng (kể cả MÔ TẢ HÌNH nếu ý đó dựa vào hình). "
    "`opening`: tình huống hoặc bài toán mở đầu của bài nếu sách có (1 đến 2 câu, giữ các con số), rỗng nếu không có; "
    "`opening_sources`: số [n] của đoạn đó. "
    "CHỈ dùng thông tin trong các đoạn, không thêm kiến thức ngoài. Viết công thức bằng ký hiệu thường (x^2, a/b, "
    "sqrt(2)), không dùng LaTeX."
)


class OutlineError(Exception):
    pass


class OutlinePoint(BaseModel):
    title: str
    content: str
    question: str
    answer: str
    sources: list[int]


class Outline(BaseModel):
    opening: str
    opening_sources: list[int]
    points: list[OutlinePoint]


@dataclass(frozen=True)
class Point:
    position: int  # 0 = mở bài, 1.. = ý chính
    title: str
    content: str
    question: str | None
    answer: str | None
    chunk_ids: tuple[int, ...]


def strip_overlap(previous: str, current: str, max_overlap: int = 600) -> str:
    """Bỏ phần đầu của `current` trùng phần cuối của `previous` (đoạn SGK được cắt gối đầu nhau để tìm kiếm)."""
    for size in range(min(len(previous), len(current), max_overlap), 20, -1):
        if previous.endswith(current[:size]):
            return current[size:].lstrip()
    return current


async def _material(lesson_id: UUID) -> tuple[str, list[tuple]]:
    async with relational.connection() as conn:
        title = await (await conn.execute("SELECT title FROM lessons WHERE id = %s", (lesson_id,))).fetchone()
        if title is None:
            raise OutlineError("lesson not found")
        rows = await (await conn.execute(
            "SELECT id, kind, page, content FROM chunks WHERE lesson_id = %s"
            " AND coalesce(review, 'approved') <> 'rejected' ORDER BY page, id", (lesson_id,))).fetchall()
    return title[0], rows


def passages(rows: list[tuple]) -> list[str]:
    """Các đoạn đánh số theo id chunk; chữ đã bỏ phần gối đầu, hình ghi rõ là mô tả hình."""
    out, previous = [], ""
    for chunk_id, kind, page, content in rows:
        if kind == "figure":
            out.append(f"[{chunk_id}] (trang {page}) MÔ TẢ HÌNH: {content}")
            continue
        text = strip_overlap(previous, content)
        previous = content
        if text:
            out.append(f"[{chunk_id}] (trang {page}) {text}")
    return out


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def to_points(outline: Outline, valid_ids: set[int]) -> list[Point]:
    """Kiểm tra kết quả LLM: bỏ ý rỗng, nguồn không thuộc bài; câu hỏi và đáp án phải đi cùng nhau."""
    points = []
    if outline.opening.strip():
        points.append(Point(0, "Mở đầu", _clip(outline.opening, 3000), None, None,
                            tuple(s for s in outline.opening_sources if s in valid_ids)))
    kept = [p for p in outline.points if p.title.strip() and p.content.strip()][:MAX_POINTS]
    for position, p in enumerate(kept, 1):
        asked = bool(p.question.strip() and p.answer.strip())
        points.append(Point(position, _clip(p.title, 200), _clip(p.content, 3000),
                            _clip(p.question, 500) if asked else None, _clip(p.answer, 500) if asked else None,
                            tuple(dict.fromkeys(s for s in p.sources if s in valid_ids))))
    return points


async def generate_outline(llm: LLMClient, lesson_id: UUID) -> list[Point]:
    """Rút dàn ý (một lượt LLM) và THAY dàn ý cũ của bài. Lỗi → OutlineError, dàn ý cũ giữ nguyên."""
    title, rows = await _material(lesson_id)
    if not rows:
        raise OutlineError("lesson has no content")
    result = await llm.complete("outline", [{"role": "user", "content": f"Bài: {title}\n\n" + "\n\n".join(passages(rows))}],
                                system=OUTLINE_SYSTEM, schema=Outline)
    if isinstance(result, Refusal):
        raise OutlineError(f"outline refused ({result.category})")
    points = to_points(result.parsed, {r[0] for r in rows})
    if not any(p.position > 0 for p in points):
        raise OutlineError("outline has no points")
    async with relational.transaction() as conn:
        await conn.execute("DELETE FROM lesson_points WHERE lesson_id = %s", (lesson_id,))
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO lesson_points (lesson_id, position, title, content, question, answer, chunk_ids)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [(lesson_id, p.position, p.title, p.content, p.question, p.answer, list(p.chunk_ids)) for p in points])
    return points


async def load_outline(lesson_id: UUID) -> list[Point]:
    async with relational.connection() as conn:
        rows = await (await conn.execute(
            "SELECT position, title, content, question, answer, chunk_ids FROM lesson_points WHERE lesson_id = %s"
            " ORDER BY position", (lesson_id,))).fetchall()
    return [Point(r[0], r[1], r[2], r[3], r[4], tuple(r[5])) for r in rows]


async def outline_document(llm: LLMClient, document_id: UUID, limit: int = 4,
                           on_lesson: Callable[[int, int], Awaitable[None]] | None = None) -> list[tuple[str, int]]:
    """Tạo dàn ý cho mọi bài của tài liệu (song song có giới hạn). Trả về [(tên bài, số ý)] theo thứ tự bài
    (0 = lỗi, bài đó giữ dàn ý cũ); danh sách chứ không phải dict vì nhiều bài trùng tên ("Luyện tập chung")."""
    async with relational.connection() as conn:
        lessons = await (await conn.execute("SELECT id, title FROM lessons WHERE document_id = %s ORDER BY position",
                                            (document_id,))).fetchall()
    gate = asyncio.Semaphore(limit)
    done = 0

    async def one(lesson_id: UUID, title: str) -> tuple[str, int]:
        nonlocal done
        async with gate:
            try:
                return title, sum(p.position > 0 for p in await generate_outline(llm, lesson_id))
            except Exception as e:  # một bài lỗi không chặn các bài khác; bài đó giảng theo đoạn SGK (đã lọc nhiễu)
                log.warning("outline failed", extra={"lesson_id": str(lesson_id), "error": str(e)})
                return title, 0
            finally:
                done += 1
                if on_lesson:
                    await on_lesson(done, len(lessons))

    return list(await asyncio.gather(*(one(lid, title) for lid, title in lessons)))


async def main(argv=None) -> int:
    from app.ai.llm import make_llm
    from app.config import get_settings

    parser = argparse.ArgumentParser(prog="python -m app.outline", description="Tạo dàn ý giảng cho một tài liệu")
    parser.add_argument("document_id", type=UUID)
    args = parser.parse_args(argv)
    settings = get_settings()
    await relational.open_pool(settings.database_url)
    try:
        for title, count in await outline_document(make_llm(settings), args.document_id):
            print(f"  {title}: {count} ý" if count else f"  {title}: LỖI (giữ dàn ý cũ / giảng theo đoạn SGK)")
    finally:
        await relational.close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
