"""Tiến độ nạp tài liệu sau bước OCR (chia bài, tìm hình, mô tả hình 120/290, dàn ý…) cho trang kiểm duyệt.

Lưu tạm trên Redis (không đổi schema). Redis lỗi thì bỏ qua: tiến độ chỉ để hiển thị, không bao giờ làm hỏng việc nạp.
"""
import logging
from uuid import UUID

from redis.asyncio import Redis

log = logging.getLogger("lusia.ingestion")
TTL_S = 3600


def key(document_id: UUID | str) -> str:
    return f"lusia:ingest:{document_id}"


class Progress:
    def __init__(self, redis_url: str, document_id: UUID):
        self._key = key(document_id)
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def report(self, text: str) -> None:
        try:
            await self._redis.set(self._key, text, ex=TTL_S)
        except Exception as e:
            log.debug("progress not reported", extra={"error": str(e)})

    async def close(self) -> None:
        try:
            await self._redis.delete(self._key)
            await self._redis.aclose()
        except Exception as e:
            log.debug("progress not cleared", extra={"error": str(e)})


async def read(redis: Redis, document_ids: list[UUID]) -> dict[UUID, str]:
    """Bước đang chạy của các tài liệu đang xử lý (thiếu = chưa có / đã xong)."""
    if not document_ids:
        return {}
    try:
        values = await redis.mget([key(d) for d in document_ids])
    except Exception:
        return {}
    return {d: v for d, v in zip(document_ids, values, strict=True) if v}
