import pytest

from app.core.storage.files import InvalidKeyError, LocalFileStore


async def test_put_get_round_trip(tmp_path):
    store = LocalFileStore(tmp_path)
    await store.put("fig/doc1/45-1.png", b"\x89PNG data", "image/png")
    assert await store.get("fig/doc1/45-1.png") == b"\x89PNG data"


async def test_delete_prefix(tmp_path):
    store = LocalFileStore(tmp_path)
    await store.put("fig/doc1/1-1.png", b"a", "image/png")
    await store.put("fig/doc1/2-1.png", b"b", "image/png")
    await store.put("fig/doc2/1-1.png", b"c", "image/png")
    await store.delete_prefix("fig/doc1/")
    assert not (tmp_path / "fig" / "doc1").exists()
    assert await store.get("fig/doc2/1-1.png") == b"c"


@pytest.mark.parametrize("key", ["../x", "fig/../../etc/passwd", "/etc/passwd", "", "a\\b"])
async def test_unsafe_keys_rejected(tmp_path, key):
    with pytest.raises(InvalidKeyError):
        await LocalFileStore(tmp_path).put(key, b"x", "text/plain")
