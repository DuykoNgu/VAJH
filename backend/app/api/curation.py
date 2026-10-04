"""Chuẩn bị tri thức: giáo viên kiểm duyệt bản nháp (đoạn văn, mô tả hình, bài học) rồi xuất bản cho học sinh.

Chỉ kiểm duyệt TRI THỨC GỐC; cách LUSIA diễn đạt (câu dẫn, hình ảnh tưởng tượng) vẫn sinh mới mỗi lần giảng.
"""
import uuid
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pgvector import Vector
from pydantic import BaseModel, Field

from app import learning, tracing
from app.agents.base import Evidence, TurnContext
from app.hooks import suggest_hooks
from app.identity import CurrentTeacher, UserContext
from app.storage import relational
from app.teaching import group_parts, lesson_parts

router = APIRouter(prefix="/curation", tags=["curation"])


class CurationDocument(BaseModel):
    id: UUID
    kind: Literal["textbook", "upload"]
    title: str
    subject: str
    grade: int
    status: Literal["processing", "ready", "failed"]
    error: str | None
    processed_pages: int
    page_count: int | None
    published: bool
    lessons: int
    text_chunks: int
    figures: int
    pending_figures: int
    created_at: datetime


class CurationPart(BaseModel):
    number: int | None  # None: hình đã từ chối, không được giảng
    kind: Literal["text", "figure"]
    chunk_id: int
    page: int
    content: str
    review: Literal["pending", "approved", "rejected"] | None
    image_url: str | None


class CurationLesson(BaseModel):
    id: UUID
    position: int
    title: str
    page_start: int
    page_end: int
    parts: list[CurationPart]


class CurationDetail(BaseModel):
    document: CurationDocument
    lessons: list[CurationLesson]


class ChunkEdit(BaseModel):
    content: str = Field(min_length=1)


class PreviewRequest(BaseModel):
    lesson_id: UUID
    part: int = Field(ge=1)


class Preview(BaseModel):
    part: int
    parts: int
    answer: str
    sentences: list[str]
    note: str = "Đây là MỘT ví dụ; mỗi lần giảng LUSIA diễn đạt khác đi, chỉ tri thức gốc là cố định."


async def _rows(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


DOC_SQL = (
    "SELECT d.id, d.kind, d.title, d.subject, d.grade, d.status, d.error, d.processed_pages, d.page_count,"
    " d.published_at IS NOT NULL, (SELECT count(*) FROM lessons l WHERE l.document_id = d.id),"
    " count(c.id) FILTER (WHERE c.kind = 'text'), count(c.id) FILTER (WHERE c.kind = 'figure'),"
    " count(c.id) FILTER (WHERE c.review = 'pending'), d.created_at"
    " FROM documents d LEFT JOIN chunks c ON c.document_id = d.id")


def _document(r) -> CurationDocument:
    return CurationDocument(id=r[0], kind=r[1], title=r[2], subject=r[3], grade=r[4], status=r[5], error=r[6],
                            processed_pages=r[7], page_count=r[8], published=r[9], lessons=r[10], text_chunks=r[11],
                            figures=r[12], pending_figures=r[13], created_at=r[14])


async def _one_document(doc_id: UUID) -> CurationDocument:
    rows = await _rows(DOC_SQL + " WHERE d.id = %s GROUP BY d.id", (doc_id,))
    if not rows:
        raise HTTPException(404, "document not found")
    return _document(rows[0])


@router.get("/documents", response_model=list[CurationDocument])
async def list_documents(teacher: UserContext = CurrentTeacher) -> list[CurationDocument]:
    # authz-later: chỉ SGK được phép sửa và tài liệu của lớp mình
    return [_document(r) for r in await _rows(DOC_SQL + " GROUP BY d.id ORDER BY d.created_at DESC")]


@router.get("/documents/{doc_id}", response_model=CurationDetail)
async def get_document(doc_id: UUID, teacher: UserContext = CurrentTeacher) -> CurationDetail:
    document = await _one_document(doc_id)
    lessons = await _rows("SELECT id, position, title, page_start, page_end FROM lessons WHERE document_id = %s"
                          " ORDER BY position", (doc_id,))
    # Cả hình đã từ chối cũng hiện (để giáo viên đổi ý); thứ tự và cách chia phần giống hệt khi giảng
    chunks = await _rows("SELECT id, kind, page, content, review, lesson_id FROM chunks WHERE document_id = %s"
                         " ORDER BY page, id", (doc_id,))
    result = []
    for lid, position, title, start, end in lessons:
        evidence = [Evidence(c[0], c[1], c[2], c[3], c[4], title) for c in chunks if c[5] == lid]
        taught = group_parts([e for e in evidence if e.review != "rejected"])  # đánh số đúng như khi giảng
        rejected = [(None, e) for e in evidence if e.review == "rejected"]
        items = sorted([(p.number, e) for p in taught for e in p.evidence] + rejected,
                       key=lambda x: (x[1].page, x[1].chunk_id, x[0] or 0))
        parts = [CurationPart(number=n, kind=e.kind, chunk_id=e.chunk_id, page=e.page, content=e.content,
                              review=e.review, image_url=f"/figures/{e.chunk_id}/image" if e.kind == "figure" else None)
                 for n, e in items]
        result.append(CurationLesson(id=lid, position=position, title=title, page_start=start, page_end=end,
                                     parts=parts))
    return CurationDetail(document=document, lessons=result)


async def _text_chunk(chunk_id: int) -> None:
    rows = await _rows("SELECT kind FROM chunks WHERE id = %s", (chunk_id,))
    if not rows:
        raise HTTPException(404, "chunk not found")
    if rows[0][0] != "text":
        raise HTTPException(409, "figures are changed through figure review")


@router.patch("/chunks/{chunk_id}", status_code=204)
async def edit_chunk(request: Request, chunk_id: int, body: ChunkEdit,
                     teacher: UserContext = CurrentTeacher) -> Response:
    # authz-later: chỉ tài liệu giáo viên được phép sửa
    await _text_chunk(chunk_id)
    text = body.content.strip()
    [vector] = await request.app.state.embeddings.embed([text])  # nội dung mới → embedding mới
    async with relational.connection() as conn:
        await conn.execute("UPDATE chunks SET content = %s, embedding = %s WHERE id = %s",
                           (text, Vector(vector), chunk_id))
    return Response(status_code=204)


@router.delete("/chunks/{chunk_id}", status_code=204)
async def delete_chunk(chunk_id: int, teacher: UserContext = CurrentTeacher) -> Response:
    # authz-later: chỉ tài liệu giáo viên được phép sửa
    await _text_chunk(chunk_id)
    async with relational.connection() as conn:
        await conn.execute("DELETE FROM chunks WHERE id = %s", (chunk_id,))
    return Response(status_code=204)


@router.post("/documents/{doc_id}/publish", response_model=CurationDocument)
async def publish(doc_id: UUID, teacher: UserContext = CurrentTeacher) -> CurationDocument:
    # authz-later: chỉ giáo viên được phép xuất bản tài liệu này
    document = await _one_document(doc_id)
    if document.status != "ready":
        raise HTTPException(409, "Tài liệu chưa xử lý xong.")
    if document.pending_figures:
        raise HTTPException(409, f"Còn {document.pending_figures} hình chưa duyệt.")
    async with relational.connection() as conn:
        # điều kiện lặp lại trong câu UPDATE: không xuất bản nếu vừa có hình mới chờ duyệt
        await conn.execute(
            "UPDATE documents SET published_at = now(), published_by = %s WHERE id = %s AND status = 'ready'"
            " AND NOT EXISTS (SELECT 1 FROM chunks WHERE document_id = %s AND review = 'pending')",
            (teacher.teacher_id, doc_id, doc_id))
    return await _one_document(doc_id)


@router.post("/documents/{doc_id}/unpublish", response_model=CurationDocument)
async def unpublish(doc_id: UUID, teacher: UserContext = CurrentTeacher) -> CurationDocument:
    await _one_document(doc_id)
    async with relational.connection() as conn:
        await conn.execute("UPDATE documents SET published_at = NULL, published_by = NULL WHERE id = %s", (doc_id,))
    return await _one_document(doc_id)


@router.post("/preview", response_model=Preview)
async def preview(request: Request, body: PreviewRequest, teacher: UserContext = CurrentTeacher) -> Preview:
    rows = await _rows("SELECT d.grade, d.subject, l.title FROM lessons l JOIN documents d ON d.id = l.document_id"
                       " WHERE l.id = %s", (body.lesson_id,))
    if not rows:
        raise HTTPException(404, "lesson not found")
    parts = await lesson_parts(body.lesson_id)  # đúng các phần học sinh sẽ học (bỏ hình đã từ chối)
    if body.part > len(parts):
        raise HTTPException(422, f"lesson has {len(parts)} parts")
    # phiên ảo: không có gì được lưu (preview=True bỏ qua câu hỏi kiểm tra và tiến độ)
    ctx = TurnContext(mode="teach", session_id=uuid.uuid4(), student_id=uuid.uuid4(), grade=rows[0][0],
                      lesson_id=body.lesson_id)
    async with tracing.trace("preview", input=f"{rows[0][2]} — phần {body.part}") as t:
        reply = await learning.teach_part(ctx, request.app.state.agents, parts, body.part, preview=True,
                                          hook_ideas=[h.spoken for h in suggest_hooks(rows[0][1], rows[0][2],
                                                                                        body.lesson_id)]
                                          if body.part == 1 else None)
        t.output = reply.answer
    return Preview(part=body.part, parts=len(parts), answer=reply.answer, sentences=reply.sentences)
