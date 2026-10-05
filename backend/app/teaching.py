"""Giảng bài theo DÀN Ý (các ý chính rút từ nguồn tri thức, app/outline.py); bài chưa có dàn ý thì giảng theo đoạn SGK
đã lọc nhiễu, cắt thành các phần nhỏ một ý (≤ ~450 ký tự, ở ranh giới câu), mỗi hình một phần.

Vị trí phần lưu trong Redis theo phiên ("trạng thái ngắn hạn của agent" trong kiến trúc LUSIA).
Câu hỏi kiểm tra của từng phần lưu vào bảng questions (câu tự luận) → tính vào lesson_mastery.
"""
import re
from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

from app.agents.base import Evidence
from app.outline import load_outline, strip_overlap
from app.storage import cache, relational

PART_CHARS = 450
SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+")
STATE_TTL_S = 24 * 3600


# Nhiễu trong SGK khi giảng theo đoạn (chưa có dàn ý): hộp mục tiêu, hoạt động, bài tập... cho tới khi gặp lại kiến thức
SKIP_FROM = re.compile(r"^(Luyện tập|Vận dụng|Thử thách|Tranh luận|Bài tập|BÀI TẬP|HĐ\s*\d|Câu hỏi|\d+\.\d+\.)"
                       r"|Khái niệm, thuật ngữ|Kiến thức, kĩ năng")
RESUME_AT = re.compile(r"^(Khái niệm\s+[^,]|Định nghĩa|Định lí|Định lý|Quy tắc|Tính chất|Chú ý|Nhận xét|Ví dụ|Ta gọi"
                       r"|Muốn\b)|\b(gọi là|là biểu thức)\b")
# OCR không có dấu câu giữa tiêu đề và hoạt động ("Khái niệm đơn thức HĐ1 Biểu thức…"): tách câu tại các mốc này
MARKER = re.compile(r"\s+(?=(HĐ\s*\d|Luyện tập\b|Vận dụng\b|Ví dụ\s*\d|Chú ý\b|Khái niệm\s|Định nghĩa\b|Quy tắc\b))")


@dataclass(frozen=True)
class Part:
    number: int                      # từ 1
    kind: Literal["text", "figure"]
    evidence: tuple[Evidence, ...]
    title: str | None = None         # theo dàn ý: tên ý ("Đơn thức là gì")
    question: str | None = None      # theo dàn ý: câu hỏi kiểm tra (từ bài luyện tập của sách) và đáp án
    answer: str | None = None


def split_ideas(text: str, max_chars: int = PART_CHARS) -> list[str]:
    """Cắt chữ thành các ý nhỏ ở ranh giới câu; một câu dài hơn giới hạn đứng riêng (không cắt giữa câu)."""
    pieces, current = [], ""
    for sentence in (s.strip() for s in SENTENCE_END.split(" ".join(text.split())) if s.strip()):
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def group_parts(chunks: list[Evidence], max_chars: int = PART_CHARS) -> list[Part]:
    """Mỗi hình là một phần; chữ được tách thành các ý nhỏ, mỗi ý một phần (vẫn giữ chunk_id để trích dẫn trang)."""
    parts: list[Part] = []
    for chunk in chunks:
        if chunk.kind == "figure":
            parts.append(Part(len(parts) + 1, "figure", (chunk,)))
            continue
        for idea in split_ideas(chunk.content, max_chars):
            parts.append(Part(len(parts) + 1, "text", (replace(chunk, content=idea),)))
    return parts


def _is_section_heading(sentence: str) -> bool:
    words = sentence.split()  # "2 ĐA THỨC THU GỌN": số mục + chữ in hoa
    return len(words) >= 2 and words[0].isdigit() and words[1].isupper() and len(words[1]) >= 2


def clean_ideas(chunks: list[Evidence], lesson_title: str | None, max_chars: int = PART_CHARS) -> list[Evidence]:
    """Giảng theo đoạn (chưa có dàn ý): bỏ phần gối đầu giữa các đoạn, lời giới thiệu chương trước tiêu đề bài, hộp mục
    tiêu, hoạt động và bài tập (tới khi gặp lại định nghĩa, quy tắc, mục mới...); hình nằm trong vùng bị bỏ cũng bỏ.
    Câu còn lại được gói thành ý ≤ max_chars XUYÊN ranh giới đoạn (tiêu đề dính vào câu sau, không còn mẩu câu lẻ);
    mỗi ý mang chunk_id của câu đầu tiên để trích dẫn trang."""
    number = re.search(r"\d+", lesson_title or "")
    heading = re.compile(rf"\bBài\s*{number.group()}(?![\d.,])") if number else None
    texts, previous = [], ""
    for chunk in chunks:
        if chunk.kind == "text":
            texts.append(strip_overlap(previous, chunk.content))
            previous = chunk.content
        else:
            texts.append(chunk.content)
    start = next(((i, m.start()) for i, (c, t) in enumerate(zip(chunks, texts, strict=True))
                  if c.kind == "text" and heading and (m := heading.search(t))), (0, 0))
    ideas: list[Evidence] = []
    owner, current, skipping = None, "", False

    def flush():
        nonlocal owner, current
        if current:
            ideas.append(replace(owner, content=current))
        owner, current = None, ""

    for i, (chunk, text) in enumerate(zip(chunks, texts, strict=True)):
        if i < start[0]:
            continue  # trước tiêu đề bài: lời giới thiệu chương
        if chunk.kind == "figure":
            if not skipping:
                flush()
                ideas.append(chunk)
            continue
        body = text[start[1]:] if i == start[0] else text
        for sentence in (piece.strip() for s in SENTENCE_END.split(body) for piece in MARKER.split(s) if piece.strip()):
            if SKIP_FROM.search(sentence):
                skipping = True
            elif skipping and not sentence.endswith("?") and (
                    RESUME_AT.search(sentence) or _is_section_heading(sentence)):
                skipping = False
            if skipping:
                continue
            if current and len(current) + 1 + len(sentence) > max_chars:
                flush()
            owner = owner or chunk
            current = f"{current} {sentence}".strip()
    flush()
    return ideas


async def lesson_parts(lesson_id: UUID) -> list[Part]:
    """Theo dàn ý nếu bài đã có (mỗi ý một phần, kèm hình nguồn); không thì theo đoạn SGK đã lọc nhiễu."""
    async with relational.connection() as conn:
        rows = await (await conn.execute(
            "SELECT c.id, c.kind, c.page, c.content, c.review, l.title FROM chunks c JOIN lessons l ON l.id = c.lesson_id"
            " WHERE c.lesson_id = %s AND coalesce(c.review, 'approved') <> 'rejected' ORDER BY c.page, c.id",
            (lesson_id,))).fetchall()
    chunks = [Evidence(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
    if not chunks:
        return []
    points = [p for p in await load_outline(lesson_id) if p.position > 0]
    if not points:
        return [Part(n, idea.kind, (idea,)) for n, idea in enumerate(clean_ideas(chunks, chunks[0].lesson_title), 1)]
    by_id = {c.chunk_id: c for c in chunks}
    parts = []
    for number, point in enumerate(points, 1):
        sources = [by_id[i] for i in point.chunk_ids if i in by_id]
        anchor = next((e for e in sources if e.kind == "text"), sources[0] if sources else chunks[0])  # trang trích dẫn
        knowledge = Evidence(anchor.chunk_id, "text", anchor.page, f"{point.title}. {point.content}", None,
                             anchor.lesson_title)
        figures = tuple(e for e in sources if e.kind == "figure")
        parts.append(Part(number, "figure" if figures else "text", (knowledge,) + figures, point.title, point.question,
                          point.answer))
    return parts


async def lesson_opening(lesson_id: UUID) -> str | None:
    """Tình huống mở đầu của sách (dàn ý, vị trí 0) để dẫn vào bài; None nếu không có."""
    return next((p.content for p in await load_outline(lesson_id) if p.position == 0), None)


def _key(session_id: UUID, name: str) -> str:
    return f"lusia:session:{session_id}:{name}"


async def get_part(session_id: UUID) -> int:
    """Phần vừa giảng gần nhất (0 = chưa giảng phần nào)."""
    value = await cache.redis().get(_key(session_id, "part"))
    return int(value) if value else 0


async def set_part(session_id: UUID, number: int) -> None:
    await cache.redis().set(_key(session_id, "part"), number, ex=STATE_TTL_S)


async def store_check_question(session_id: UUID, student_id: UUID, lesson_id: UUID, question: str,
                               expected: str, focus: str) -> None:
    """Câu hỏi kiểm tra của một phần → quiz "học theo phần" của phiên (tạo khi cần), câu tự luận (choices NULL)."""
    key = _key(session_id, "walkquiz")
    remembered = await cache.redis().get(key)
    async with relational.transaction() as conn:
        quiz_id = None
        if remembered:  # quiz có thể đã bị xóa (đặt lại dữ liệu demo) → kiểm tra lại
            row = await (await conn.execute("SELECT id FROM quizzes WHERE id = %s", (remembered,))).fetchone()
            quiz_id = row[0] if row else None
        if quiz_id is None:
            quiz_id = (await (await conn.execute(
                "INSERT INTO quizzes (student_id, lesson_id, session_id) VALUES (%s, %s, %s) RETURNING id",
                (student_id, lesson_id, session_id))).fetchone())[0]
        position = (await (await conn.execute("SELECT count(*) + 1 FROM questions WHERE quiz_id = %s",
                                              (quiz_id,))).fetchone())[0]
        await conn.execute("INSERT INTO questions (quiz_id, position, prompt, focus, choices, correct_answer, explanation)"
                           " VALUES (%s, %s, %s, %s, NULL, %s, %s)", (quiz_id, position, question, focus, expected, expected))
    await cache.redis().set(key, str(quiz_id), ex=STATE_TTL_S)  # chỉ ghi nhớ sau khi commit
