"""Worker chạy background job (arq, hàng đợi trên Redis):  arq app.worker.WorkerSettings

Job nhận id tường minh trong tham số, không bao giờ tự xác định danh tính người dùng.
"""
from functools import wraps

from arq import Retry
from arq.connections import RedisSettings

from app.config import get_settings

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


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
