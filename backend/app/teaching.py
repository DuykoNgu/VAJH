"""Giảng bài theo từng phần nhỏ: mỗi phần MỘT ý (≤ ~450 ký tự, cắt ở ranh giới câu), mỗi hình một phần.

Phần ngắn để người học chỉ bằng tai không bị "loãng" và nhớ được.

Vị trí phần lưu trong Redis theo phiên ("trạng thái ngắn hạn của agent" trong kiến trúc LUSIA).
Câu hỏi kiểm tra của từng phần lưu vào bảng questions (câu tự luận) → tính vào lesson_mastery.
"""
import re
from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

from app.agents.base import Evidence
from app.storage import cache, relational

PART_CHARS = 450
SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+")
STATE_TTL_S = 24 * 3600


@dataclass(frozen=True)
class Part:
    number: int                      # từ 1
    kind: Literal["text", "figure"]
    evidence: tuple[Evidence, ...]


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


async def lesson_parts(lesson_id: UUID) -> list[Part]:
    async with relational.connection() as conn:
        rows = await (await conn.execute(
            "SELECT c.id, c.kind, c.page, c.content, c.review, l.title FROM chunks c JOIN lessons l ON l.id = c.lesson_id"
            " WHERE c.lesson_id = %s AND coalesce(c.review, 'approved') <> 'rejected' ORDER BY c.page, c.id",
            (lesson_id,))).fetchall()
    return group_parts([Evidence(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows])


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
