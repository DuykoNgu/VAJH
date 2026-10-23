"""Tài liệu học tập: tải lên PDF, theo dõi xử lý, xem bài học, sửa bài học, tải file / ảnh hình."""
import uuid
from datetime import datetime
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core import jobs
from app.core.identity import CurrentTeacher, CurrentUser, UserContext
from app.core.storage import relational
from app.features.documents.ingest import SUBJECTS
from app.features.documents.ingestion.lessons import (
    LessonRange,
    LessonRangeError,
    unit_heading,
    validate_ranges,
)
from app.features.documents.ingestion.pdf import PdfError, open_pdf

router = APIRouter(tags=["documents"])
Subject = Literal[tuple(SUBJECTS)]  # type: ignore[valid-type]


class DocumentSummary(BaseModel):
    id: UUID
    kind: Literal["textbook", "upload"]
    title: str
    subject: str
    grade: int
    status: Literal["processing", "ready", "failed"]
    created_at: datetime


class DocumentDetail(DocumentSummary):
    page_count: int | None
    processed_pages: int
    skipped_figures: int
    error: str | None
    lessons: int
    text_chunks: int
    figure_chunks: int
    pending_figures: int


class Lesson(BaseModel):
    id: UUID
    position: int
    title: str
    page_start: int
    page_end: int
    unit: str | None = None  # "Chủ đề 2: Số thập phân"; None = sách không ghi chủ đề/chương trước bài này


class LessonInput(BaseModel):
    id: UUID | None = None
    title: str = Field(min_length=1)
    page_start: int
    page_end: int


class Accepted(BaseModel):
    id: UUID
    status: str


def _files(request: Request):
    return request.app.state.files


def _settings(request: Request):
    return request.app.state.settings


async def _fetch(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


async def _require_document(doc_id: UUID):
    rows = await _fetch("SELECT storage_key, page_count, status FROM documents WHERE id = %s", (doc_id,))
    if not rows:
        raise HTTPException(404, "document not found")
    return rows[0]


@router.post("/documents", status_code=202, response_model=Accepted)
async def upload_document(request: Request, file: UploadFile, title: str = Form(min_length=1),
                          subject: Subject = Form(), grade: int = Form(ge=1, le=12),
                          user: UserContext = CurrentUser) -> Accepted:
    return await store_upload(request, file, title, subject, grade, user)


async def store_upload(request: Request, file: UploadFile, title: str, subject: str, grade: int,
                       user: UserContext) -> Accepted:
    """Kiểm tra PDF, lưu file, tạo tài liệu (chủ = người tải lên) và xếp hàng xử lý."""
    settings = _settings(request)
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"file larger than {settings.max_upload_mb} MB")
    try:
        open_pdf(data, settings.max_pages).close()
    except PdfError as e:
        raise HTTPException(422, str(e)) from None
    doc_id = uuid.uuid4()
    key = f"uploads/{user.user_id}/{doc_id}.pdf"  # người tải lên luôn lấy từ danh tính, không từ body
    await _files(request).put(key, data, "application/pdf")
    async with relational.connection() as conn:
        await conn.execute("INSERT INTO documents (id, kind, title, subject, grade, storage_key, uploaded_by)"
                           " VALUES (%s, 'upload', %s, %s, %s, %s, %s)",
                           (doc_id, title, subject, grade, key, user.user_id))
    await jobs.enqueue("ingest_document", str(doc_id))
    return Accepted(id=doc_id, status="processing")


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(subject: Subject | None = None, grade: int | None = None,
                         user: UserContext = CurrentUser) -> list[DocumentSummary]:
    # authz-later: giáo viên thấy cả tài liệu học sinh lớp mình tải lên
    rows = await _fetch(
        "SELECT id, kind, title, subject, grade, status, created_at FROM documents"
        " WHERE (published_at IS NOT NULL OR uploaded_by = %s)"  # bản nháp: chỉ người tải lên (và trang kiểm duyệt) thấy
        " AND (%s::subject IS NULL OR subject = %s::subject) AND (%s::smallint IS NULL OR grade = %s::smallint)"
        " ORDER BY created_at DESC", (user.user_id, subject, subject, grade, grade))
    return [DocumentSummary(id=r[0], kind=r[1], title=r[2], subject=r[3], grade=r[4], status=r[5], created_at=r[6])
            for r in rows]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: UUID, user: UserContext = CurrentUser) -> DocumentDetail:
    # authz-later: chỉ chủ tài liệu, giáo viên của chủ tài liệu, hoặc SGK
    rows = await _fetch(
        "SELECT d.id, d.kind, d.title, d.subject, d.grade, d.status, d.created_at, d.page_count, d.processed_pages,"
        " d.skipped_figures, d.error,"
        " (SELECT count(*) FROM lessons l WHERE l.document_id = d.id),"
        " count(c.id) FILTER (WHERE c.kind = 'text'), count(c.id) FILTER (WHERE c.kind = 'figure'),"
        " count(c.id) FILTER (WHERE c.review = 'pending')"
        " FROM documents d LEFT JOIN chunks c ON c.document_id = d.id WHERE d.id = %s GROUP BY d.id", (doc_id,))
    if not rows:
        raise HTTPException(404, "document not found")
    r = rows[0]
    return DocumentDetail(id=r[0], kind=r[1], title=r[2], subject=r[3], grade=r[4], status=r[5], created_at=r[6],
                          page_count=r[7], processed_pages=r[8], skipped_figures=r[9], error=r[10], lessons=r[11],
                          text_chunks=r[12], figure_chunks=r[13], pending_figures=r[14])


@router.get("/documents/{doc_id}/file")
async def get_document_file(request: Request, doc_id: UUID, user: UserContext = CurrentUser) -> Response:
    # authz-later: chỉ chủ tài liệu, giáo viên của chủ tài liệu, hoặc SGK
    key, *_ = await _require_document(doc_id)
    return Response(await _files(request).get(key), media_type="application/pdf")


async def _lessons(doc_id: UUID) -> list[Lesson]:
    # Chủ đề đọc từ đoạn văn đầu trang mở bài (không lưu riêng: sửa bài / nạp lại sách vẫn đúng); bài không mở
    # chủ đề mới thuộc chủ đề của bài trước.
    rows = await _fetch(
        "SELECT l.id, l.position, l.title, l.page_start, l.page_end,"
        " (SELECT c.content FROM chunks c WHERE c.lesson_id = l.id AND c.page = l.page_start AND c.kind = 'text'"
        "  ORDER BY c.id LIMIT 1)"
        " FROM lessons l WHERE l.document_id = %s ORDER BY l.position", (doc_id,))
    lessons, unit = [], None
    for r in rows:
        unit = unit_heading(r[5] or "") or unit
        lessons.append(Lesson(id=r[0], position=r[1], title=r[2], page_start=r[3], page_end=r[4], unit=unit))
    return lessons


@router.get("/documents/{doc_id}/lessons", response_model=list[Lesson])
async def get_lessons(doc_id: UUID, user: UserContext = CurrentUser) -> list[Lesson]:
    # authz-later: chỉ chủ tài liệu, giáo viên của chủ tài liệu, hoặc SGK
    await _require_document(doc_id)
    return await _lessons(doc_id)


async def _rebuild(doc_id: UUID, conn) -> None:
    # xử lý lại → về bản nháp, giáo viên phải kiểm duyệt và xuất bản lại
    await conn.execute("UPDATE documents SET status = 'processing', error = NULL, published_at = NULL,"
                       " published_by = NULL, updated_at = now() WHERE id = %s", (doc_id,))


@router.put("/documents/{doc_id}/lessons", status_code=202, response_model=list[Lesson])
async def replace_lessons(doc_id: UUID, items: list[LessonInput], teacher: UserContext = CurrentTeacher):
    # authz-later: giáo viên phải là người tải lên, hoặc được phép sửa SGK
    _, page_count, _ = await _require_document(doc_id)
    if page_count is None:
        raise HTTPException(409, "document has not been processed yet")
    try:
        validate_ranges([LessonRange(i.title, i.page_start, i.page_end) for i in items], page_count)
    except LessonRangeError as e:
        raise HTTPException(422, str(e)) from None
    existing = {r[0]: r[1] for r in await _fetch("SELECT id, title FROM lessons WHERE document_id = %s", (doc_id,))}
    unknown = [str(i.id) for i in items if i.id is not None and i.id not in existing]
    if unknown:
        raise HTTPException(422, f"lessons not in this document: {', '.join(unknown)}")
    omitted = [lid for lid in existing if lid not in {i.id for i in items}]
    try:
        async with relational.transaction() as conn:
            if omitted:
                await conn.execute("DELETE FROM lessons WHERE id = ANY(%s)", (omitted,))
            # đổi thứ tự an toàn với UNIQUE(document_id, position): tạm đẩy sang số âm trước
            await conn.execute("UPDATE lessons SET position = -position WHERE document_id = %s", (doc_id,))
            for position, item in enumerate(items, 1):
                if item.id is not None:
                    await conn.execute("UPDATE lessons SET position = %s, title = %s, page_start = %s, page_end = %s"
                                       " WHERE id = %s", (position, item.title, item.page_start, item.page_end, item.id))
                else:
                    await conn.execute("INSERT INTO lessons (document_id, position, title, page_start, page_end)"
                                       " VALUES (%s, %s, %s, %s, %s)",
                                       (doc_id, position, item.title, item.page_start, item.page_end))
            await _rebuild(doc_id, conn)
    except psycopg.errors.ForeignKeyViolation:
        titles = ", ".join(existing[lid] for lid in omitted)
        raise HTTPException(409, f"cannot delete lessons with quiz results: {titles}") from None
    await jobs.enqueue("ingest_document", str(doc_id))
    return await _lessons(doc_id)


@router.post("/documents/{doc_id}/reprocess", status_code=202, response_model=Accepted)
async def reprocess_document(doc_id: UUID, teacher: UserContext = CurrentTeacher) -> Accepted:
    # authz-later: giáo viên phải là người tải lên, hoặc được phép sửa SGK
    await _require_document(doc_id)
    async with relational.connection() as conn:
        await _rebuild(doc_id, conn)
    await jobs.enqueue("ingest_document", str(doc_id))
    return Accepted(id=doc_id, status="processing")


@router.get("/figures/{chunk_id}/image")
async def get_figure_image(request: Request, chunk_id: int, user: UserContext = CurrentUser) -> Response:
    # authz-later: chỉ chủ tài liệu, giáo viên của chủ tài liệu, hoặc SGK
    rows = await _fetch("SELECT image_key FROM chunks WHERE id = %s AND kind = 'figure'", (chunk_id,))
    if not rows:
        raise HTTPException(404, "figure not found")
    return Response(await _files(request).get(rows[0][0]), media_type="image/png")
