from pgvector import Vector
import pytest

from app.storage import relational


@pytest.fixture
async def pool(test_database):
    await relational.open_pool(test_database)
    yield relational.pool()
    await relational.close_pool()


async def test_vector_query_repeated_through_pool(pool, db):
    doc = db.execute("INSERT INTO documents (kind, title, subject, grade, storage_key)"
                     " VALUES ('textbook', 'T', 'toan', 8, 'k') RETURNING id").fetchone()[0]
    for i, val in enumerate([0.1, 0.5, 0.9]):
        db.execute("INSERT INTO chunks (document_id, page, kind, content, embedding)"
                   " VALUES (%s, 1, 'text', %s, array_fill(%s::real, ARRAY[1536])::vector)", (doc, f"c{i}", val))
    query = Vector([0.9] * 1535 + [0.1])
    for _ in range(20):  # nhiều lần liên tiếp: không lỗi prepared statement
        async with relational.connection() as conn:
            rows = await (await conn.execute(
                "SELECT content, embedding <-> %s AS d FROM chunks ORDER BY d LIMIT 3", (query,))).fetchall()
        assert [r[0] for r in rows] == ["c2", "c1", "c0"]


async def test_transaction_rolls_back_on_error(pool, db):
    with pytest.raises(RuntimeError):
        async with relational.transaction() as conn:
            await conn.execute("INSERT INTO users (full_name, username, password_hash) VALUES ('X', 'xx1', '!')")
            raise RuntimeError("boom")
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0
