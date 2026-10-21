"""RAG, phía ghi: văn bản đem embed và ghi chunk (kèm embedding) vào bảng chunks.

Lúc nạp sách và lúc giáo viên sửa một chunk đều đi qua đây, nên embedding luôn được tạo theo cùng một quy tắc.
"""
from typing import Literal
from uuid import UUID

from pgvector import Vector
from psycopg import AsyncConnection

from app.core.rag.embeddings import EmbeddingClient

ChunkKind = Literal["text", "figure"]
# (lesson_id, page, kind, content, embedding, image_key, review)
ChunkRow = tuple[UUID | None, int, ChunkKind, str, list[float], str | None, str | None]

INSERT_SQL = ("INSERT INTO chunks (document_id, lesson_id, page, kind, content, embedding, image_key, review)"
              " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")


def embedding_text(kind: ChunkKind, content: str, lesson_title: str | None) -> str:
    """Đoạn chữ thêm tên bài để tìm theo chủ đề tốt hơn (content lưu nguyên văn); mô tả hình embed nguyên văn."""
    return f"{lesson_title}\n{content}" if kind == "text" and lesson_title else content


async def replace_document_chunks(conn: AsyncConnection, document_id: UUID, rows: list[ChunkRow]) -> None:
    """Thay toàn bộ chunk của tài liệu; gọi trong transaction của bước lưu."""
    await conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
    async with conn.cursor() as cur:
        await cur.executemany(INSERT_SQL, [(document_id, lesson, page, kind, content, Vector(v), key, review)
                                           for lesson, page, kind, content, v, key, review in rows])


async def reindex_chunk(conn: AsyncConnection, embeddings: EmbeddingClient, chunk_id: int, content: str) -> None:
    """Đổi nội dung một chunk và embed lại."""
    kind, title = await (await conn.execute(
        "SELECT c.kind, l.title FROM chunks c LEFT JOIN lessons l ON l.id = c.lesson_id WHERE c.id = %s",
        (chunk_id,))).fetchone()
    [vector] = await embeddings.embed([embedding_text(kind, content, title)])
    await conn.execute("UPDATE chunks SET content = %s, embedding = %s WHERE id = %s",
                       (content, Vector(vector), chunk_id))
