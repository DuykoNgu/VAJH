"""Liveness (/health) và readiness (/health/ready) - không cần danh tính."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.storage import cache, relational

router = APIRouter(tags=["health"])
TIMEOUT_S = 2


@router.get("/health")
def health():
    return {"status": "ok"}


async def _postgres():
    async with relational.connection() as conn:
        await conn.execute("SELECT 1")


async def _redis():
    await cache.redis().ping()


async def _check(probe) -> str:
    try:
        await asyncio.wait_for(probe(), TIMEOUT_S)
        return "ok"
    except Exception as e:  # noqa: BLE001 - báo lỗi của từng dependency, không làm hỏng cả endpoint
        return f"error: {type(e).__name__}"


@router.get("/health/ready")
async def ready():
    pg, rd = await asyncio.gather(_check(_postgres), _check(_redis))
    # ponytail: object storage đang pending (chưa chọn server S3) -> chưa kiểm tra; thêm probe khi có storage
    checks = {"postgres": pg, "redis": rd, "storage": "not_configured"}
    healthy = pg == "ok" and rd == "ok"
    return JSONResponse({"status": "ok" if healthy else "unavailable", "checks": checks},
                        status_code=200 if healthy else 503)
