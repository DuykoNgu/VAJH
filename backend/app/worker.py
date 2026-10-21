"""Worker chạy background job (arq, hàng đợi trên Redis):  arq app.worker.WorkerSettings

Job nhận id tường minh trong tham số, không bao giờ tự xác định danh tính người dùng.
"""
import logging
from dataclasses import asdict
from functools import wraps
from uuid import UUID

from arq import Retry, cron, func
from arq.connections import RedisSettings

from app.config import get_settings
from app.core import tracing
from app.core.storage import relational
from app.features.documents.ingestion.pipeline import (
    Deps,
    IngestionError,
    mark_failed,
    process_document,
)

log = logging.getLogger("lusia.worker")

MAX_TRIES = 3
RETRY_BASE_S = 2.0  # thử lại sau 2s, 4s, ...


def retrying(fn):
    """arq chỉ thử lại khi job raise Retry: đổi lỗi bất ngờ thành Retry cho tới lần thử cuối."""

    @wraps(fn)
    async def wrapper(ctx, *args, **kwargs):
        try:
            return await fn(ctx, *args, **kwargs)
        except Retry:
            raise
        except Exception as e:
            if ctx["job_try"] < MAX_TRIES:
                raise Retry(defer=RETRY_BASE_S * 2 ** (ctx["job_try"] - 1)) from e
            raise

    return wrapper


@retrying
async def ping(ctx, value: str = "pong") -> str:
    return value


async def ingest_document(ctx, document_id: str) -> dict | None:
    """Nạp một tài liệu. Lỗi tạm thời → thử lại; lỗi file PDF hoặc lần thử cuối → documents.status = failed."""
    doc_id = UUID(document_id)
    try:
        return asdict(await process_document(doc_id, ctx["deps"]))
    except IngestionError as e:
        if e.step != "parse" and ctx["job_try"] < MAX_TRIES:
            raise Retry(defer=RETRY_BASE_S * 2 ** (ctx["job_try"] - 1)) from e
        log.error("ingestion failed", extra={"document_id": document_id, "error": str(e)})
        await mark_failed(doc_id, str(e))
        return None


async def purge_traces(ctx) -> dict:
    """Hằng ngày: bỏ nội dung trace cũ (lời học sinh, prompt) và xoá trace quá hạn."""
    settings = get_settings()
    return await tracing.purge(settings.trace_payload_days, settings.trace_keep_days)


async def startup(ctx) -> None:
    settings = get_settings()
    await relational.open_pool(settings.database_url)
    ctx["deps"] = Deps.from_settings(settings)


async def shutdown(ctx) -> None:
    await relational.close_pool()


class WorkerSettings:
    functions = [ping, func(ingest_document, name="ingest_document", timeout=get_settings().ingest_timeout_s)]
    cron_jobs = [cron(purge_traces, hour=3, minute=0)]  # 03:00 mỗi ngày
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
