import os

from app.storage import cache


async def test_set_get():
    r = cache.open_redis(os.environ["REDIS_URL"])
    try:
        await r.set("lusia:test:key", "xin chào", ex=10)
        assert await cache.redis().get("lusia:test:key") == "xin chào"
    finally:
        await r.delete("lusia:test:key")
        await cache.close_redis()
