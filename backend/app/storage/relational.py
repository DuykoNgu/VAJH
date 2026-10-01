"""Relational DB (PostgreSQL + pgvector): pool kết nối dùng chung cho toàn app.

prepare_threshold=None: không dùng prepared statement phía server, để chạy được qua
pooler chế độ transaction của Neon (PgBouncer).
"""
from contextlib import asynccontextmanager

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


async def _configure(conn: AsyncConnection) -> None:
    await register_vector_async(conn)
    await conn.set_autocommit(True)


async def open_pool(url: str, min_size: int = 1, max_size: int = 10) -> AsyncConnectionPool:
    global _pool
    _pool = AsyncConnectionPool(
        url, min_size=min_size, max_size=max_size, open=False,
        kwargs={"prepare_threshold": None}, configure=_configure,
    )
    await _pool.open(wait=True)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool is not open (app lifespan not started?)")
    return _pool


@asynccontextmanager
async def connection():
    """Một kết nối autocommit từ pool (mỗi câu lệnh tự commit)."""
    async with pool().connection() as conn:
        yield conn


@asynccontextmanager
async def transaction():
    """Một kết nối trong transaction: commit khi thoát bình thường, rollback khi có lỗi."""
    async with pool().connection() as conn:
        async with conn.transaction():
            yield conn
