"""Nạp một tài liệu: PDF → chữ (OCR khi cần) → bài học → chunk + hình (mô tả) → embedding → ghi DB.

Mọi việc tốn kém làm TRƯỚC; cuối cùng hoán đổi toàn bộ lessons/chunks trong MỘT transaction. Lỗi giữa chừng
không để lại tài liệu nửa cũ nửa mới, và khi xử lý lại thì chunk cũ vẫn dùng được tới lúc hoán đổi.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from uuid import UUID

from pgvector import Vector

from app import tracing
from app.ai.embeddings import EmbeddingClient, make_embeddings
from app.ai.llm import LLMClient, make_llm
from app.config import Settings
from app.ingestion.chunking import chunk_document, embedding_text
from app.ingestion.figures import Figure, extract_figures
from app.ingestion.lessons import LessonRange, segment
from app.ingestion import scan
from app.ingestion.progress import Progress
from app.ingestion.pdf import bookmarks, open_pdf, page_texts
from app.outline import outline_document
from app.storage import relational
from app.storage.files import FileStore, make_file_store
from app.tools import FigureDescription, describe_figure, read_document

log = logging.getLogger("lusia.ingestion")


class IngestionError(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(f"{step}: {message}")
        self.step = step


@dataclass
class Deps:
    settings: Settings
    llm: LLMClient
    embeddings: EmbeddingClient
    files: FileStore

    @classmethod
    def from_settings(cls, settings: Settings) -> "Deps":
        return cls(settings, make_llm(settings), make_embeddings(settings), make_file_store(settings))


@dataclass
class Summary:
    document_id: str
    pages: int
    ocr_pages: int
    lessons: int
    lesson_source: str
    text_chunks: int
    figure_chunks: int
    skipped_figures: int
    decorative_figures: int
    outlined_lessons: int = 0  # bài đã có dàn ý giảng


async def _execute(sql: str, params=()) -> None:
    async with relational.connection() as conn:
        await conn.execute(sql, params)


async def mark_failed(document_id: UUID, error: str) -> None:
    await _execute("UPDATE documents SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
                   (error[:2000], document_id))


async def _load(document_id: UUID):
    async with relational.connection() as conn:
        doc = await (await conn.execute(
            "SELECT title, storage_key FROM documents WHERE id = %s", (document_id,))).fetchone()
        if doc is None:
            raise IngestionError("load", f"document {document_id} not found")
        lessons = await (await conn.execute(
            "SELECT id, title, page_start, page_end FROM lessons WHERE document_id = %s ORDER BY position",
            (document_id,))).fetchall()
        old_keys = [r[0] for r in await (await conn.execute(
            "SELECT image_key FROM chunks WHERE document_id = %s AND kind = 'figure'", (document_id,))).fetchall()]
    return doc, [LessonRange(t, s, e, i) for i, t, s, e in lessons], old_keys


def _lesson_of(page: int, lessons: list[LessonRange]) -> int | None:
    return next((i for i, l in enumerate(lessons) if l.page_start <= page <= l.page_end), None)


async def process_document(document_id: UUID, deps: Deps) -> Summary:
    """Nạp tài liệu trong một trace "ingest" (mọi lượt OCR / mục lục / mô tả hình xem được ở /monitor)."""
    async with tracing.trace("ingest", document_id=document_id) as t:
        summary = await _process_document(document_id, deps)
        t.output = json.dumps(asdict(summary), ensure_ascii=False)
        return summary


async def _process_document(document_id: UUID, deps: Deps) -> Summary:
    status = Progress(deps.settings.redis_url, document_id)  # bước đang chạy, cho trang kiểm duyệt
    try:
        return await _run(document_id, deps, status)
    finally:
        await status.close()


async def _run(document_id: UUID, deps: Deps, status: Progress) -> Summary:
    s = deps.settings
    step, pdf = "load", None
    try:
        (title, storage_key), lessons, old_figure_keys = await _load(document_id)
        data = await deps.files.get(storage_key)
        step = "parse"
        log.info("step", extra={"step": step})
        pdf = open_pdf(data, s.max_pages)
        await _execute("UPDATE documents SET page_count = %s, processed_pages = 0, updated_at = now() WHERE id = %s",
                       (pdf.page_count, document_id))
        pages = await asyncio.to_thread(page_texts, pdf)
        limit = asyncio.Semaphore(s.llm_concurrency)

        async def progress(done: int):
            await _execute("UPDATE documents SET processed_pages = %s WHERE id = %s", (done, document_id))

        step = "ocr"

        log.info("step", extra={"step": step})
        texts, ocr_pages = await read_document(pdf, pages, deps.llm, limit=limit, on_page=progress,
                                               local_ocr=scan.local_ocr if s.local_ocr else None)

        step = "lessons"

        log.info("step", extra={"step": step})

        await status.report("Đang chia bài theo mục lục")
        reuse_lessons = bool(lessons)  # xử lý lại: giữ nguyên bài học (và id) đã có
        source = "existing"
        if not reuse_lessons:
            lessons, source = await segment(deps.llm, title, texts, bookmarks(pdf))
        text_chunks = chunk_document(texts, lessons, s.chunk_max_chars, s.chunk_overlap_chars)

        step = "figures"

        log.info("step", extra={"step": step})
        found: list[Figure] = []
        for page in pdf:
            await status.report(f"Đang tìm hình trang {page.number + 1}/{pdf.page_count}")
            if _lesson_of(page.number + 1, lessons) is None:
                continue  # bìa, lời nói đầu, mục lục: không giảng → không tốn lượt mô tả hình, không chặn xuất bản
            if scan.is_scanned(page):  # cả trang là ảnh: model bố cục khoanh hình (tách nét vẽ không dùng được)
                started = time.perf_counter()
                on_page = await asyncio.to_thread(scan.detect_figures, page, s.layout_model_path,
                                                  s.figure_min_area_ratio)
                found += on_page
                log.info("layout page", extra={"page": page.number + 1, "figures": len(on_page),
                                               "seconds": round(time.perf_counter() - started, 2)})
            else:
                found += await asyncio.to_thread(extract_figures, page, s.figure_min_area_ratio)
        skipped = described_count = 0

        async def describe(fig: Figure) -> FigureDescription | None:
            nonlocal skipped, described_count
            async with limit:
                try:
                    return await describe_figure(deps.llm, fig.png, texts[fig.page - 1])
                except Exception as e:  # một hình lỗi không làm mất cả tài liệu
                    skipped += 1
                    log.warning("figure skipped", extra={"document_id": str(document_id), "page": fig.page,
                                                         "error": str(e)})
                    return False
                finally:
                    described_count += 1
                    await status.report(f"Đang mô tả hình {described_count}/{len(found)}")

        await status.report(f"Đang mô tả hình 0/{len(found)}")

        described = await asyncio.gather(*(describe(f) for f in found))
        figures = [(f, d) for f, d in zip(found, described, strict=True) if d]
        decorative = sum(d is None for d in described)
        run = uuid.uuid4().hex[:8]
        keys = [f"fig/{document_id}/{run}/{f.page}-{f.index}.png" for f, _ in figures]
        for key, (fig, _) in zip(keys, figures, strict=True):
            await deps.files.put(key, fig.png, "image/png")

        step = "embed"

        log.info("step", extra={"step": step})

        await status.report("Đang tạo embedding")
        vectors = await deps.embeddings.embed(
            [embedding_text(c.content, lessons[c.lesson].title if c.lesson is not None else None) for c in text_chunks]
            + [d.description for _, d in figures])

        step = "store"

        log.info("step", extra={"step": step})

        await status.report("Đang lưu")
        async with relational.transaction() as conn:
            if not reuse_lessons:
                ids = []
                for position, lesson in enumerate(lessons, 1):
                    row = await (await conn.execute(
                        "INSERT INTO lessons (document_id, position, title, page_start, page_end)"
                        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                        (document_id, position, lesson.title, lesson.page_start, lesson.page_end))).fetchone()
                    ids.append(row[0])
                lessons = [LessonRange(l.title, l.page_start, l.page_end, i) for l, i in zip(lessons, ids, strict=True)]
            await conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            rows = [(document_id, lessons[c.lesson].id if c.lesson is not None else None, c.page, "text", c.content,
                     Vector(v), None, None) for c, v in zip(text_chunks, vectors[:len(text_chunks)], strict=True)]
            for (fig, desc), key, v in zip(figures, keys, vectors[len(text_chunks):], strict=True):
                lesson = _lesson_of(fig.page, lessons)
                rows.append((document_id, lessons[lesson].id if lesson is not None else None, fig.page, "figure",
                             desc.description, Vector(v), key, "pending"))
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO chunks (document_id, lesson_id, page, kind, content, embedding, image_key, review)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", rows)
            await conn.execute(
                "UPDATE documents SET status = 'ready', error = NULL, processed_pages = page_count,"
                " skipped_figures = %s, updated_at = now() WHERE id = %s", (skipped, document_id))
        outlined = 0
        if s.outline_on_ingest:  # tài liệu đã sẵn sàng; dàn ý lỗi thì bài đó giảng theo đoạn SGK đã lọc nhiễu
            step = "outline"
            log.info("step", extra={"step": step})
            try:
                async def outlined_one(done: int, total: int) -> None:
                    await status.report(f"Đang rút dàn ý {done}/{total} bài")

                outlined = sum(n > 0 for _, n in await outline_document(deps.llm, document_id, s.llm_concurrency,
                                                                        on_lesson=outlined_one))
            except Exception as e:
                log.warning("outline step failed", extra={"document_id": str(document_id), "error": str(e)})
    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(step, str(e) or type(e).__name__) from e
    finally:
        if pdf is not None:
            page_count = pdf.page_count
            pdf.close()

    for prefix in {k.rsplit("/", 1)[0] for k in old_figure_keys} - {f"fig/{document_id}/{run}"}:
        await deps.files.delete_prefix(prefix + "/")  # ảnh của lần xử lý trước, giờ không chunk nào dùng
    summary = Summary(str(document_id), page_count, ocr_pages, len(lessons), source, len(text_chunks),
                      len(figures), skipped, decorative, outlined)
    log.info("document ingested", extra=asdict(summary))
    return summary
