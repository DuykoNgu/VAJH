"""Đưa job vào hàng đợi từ API. Tham số job phải là id/giá trị tường minh (vd. uploaded_by).

Kết nối được mở lúc enqueue đầu tiên, để API vẫn khởi động (và /health/ready báo lỗi) khi Redis tạm chết.
"""
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

_url: str | None = None
_pool: ArqRedis | None = None


def configure_queue(redis_url: str) -> None:
    global _url
    _url = redis_url


async def queue() -> ArqRedis:
    global _pool
    if _pool is None:
        if _url is None:
            raise RuntimeError("job queue is not configured (app lifespan not started?)")
        _pool = await create_pool(RedisSettings.from_dsn(_url))
    return _pool


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(function: str, *args, **kwargs) -> str:
    job = await (await queue()).enqueue_job(function, *args, **kwargs)
    return job.job_id
