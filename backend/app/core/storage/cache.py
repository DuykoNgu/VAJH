"""Redis: session state, cache, hàng đợi job (arq)."""
from redis.asyncio import Redis

_redis: Redis | None = None


def open_redis(url: str) -> Redis:
    global _redis
    _redis = Redis.from_url(url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def redis() -> Redis:
    if _redis is None:
        raise RuntimeError("redis client is not open (app lifespan not started?)")
    return _redis
