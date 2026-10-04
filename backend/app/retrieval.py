"""RAG: tìm đoạn SGK (chữ + mô tả hình) gần nghĩa nhất với câu hỏi, trong phạm vi bài học đang học."""
from uuid import UUID

from pgvector import Vector

from app.agents.base import Evidence
from app.ai.embeddings import EmbeddingClient
from app.storage import relational

SEARCH_SQL = """
SELECT c.id, c.kind, c.page, c.content, c.review, l.title
FROM chunks c LEFT JOIN lessons l ON l.id = c.lesson_id
WHERE (%(lesson)s::uuid IS NULL OR c.lesson_id = %(lesson)s::uuid)
  AND coalesce(c.review, 'approved') <> 'rejected'       -- hình bị giáo viên từ chối không bao giờ dùng
ORDER BY c.embedding <=> %(query)s
LIMIT %(k)s
"""


async def search_knowledge(embeddings: EmbeddingClient, query: str, lesson_id: UUID | None = None,
                           k: int = 6) -> list[Evidence]:
    """k đoạn gần nhất (cosine); hình `pending` vẫn trả về nhưng được đánh dấu chưa duyệt."""
    [vector] = await embeddings.embed([query])
    async with relational.connection() as conn:
        rows = await (await conn.execute(SEARCH_SQL, {"lesson": lesson_id, "query": Vector(vector), "k": k})).fetchall()
    return [Evidence(chunk_id=r[0], kind=r[1], page=r[2], content=r[3], review=r[4], lesson_title=r[5]) for r in rows]
