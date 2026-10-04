"""Lưu file (PDF, ảnh hình). Hiện dùng ổ đĩa local; S3 thêm sau (foundations task 3.3) cùng interface.

Key theo bố cục chung: sgk/<document_id>.pdf, uploads/<user_id>/<document_id>.pdf, fig/<document_id>/<page>-<n>.png
File được trả qua API, nên nơi gọi không phụ thuộc backend lưu trữ.
"""
import asyncio
import shutil
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.config import Settings


class InvalidKeyError(ValueError):
    pass


class FileStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete_prefix(self, prefix: str) -> None: ...


def _check_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
        raise InvalidKeyError(f"invalid storage key: {key!r}")
    return path


class LocalFileStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root.joinpath(*_check_key(key).parts)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)

        def write():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # ghi nguyên tử: không ai đọc được file ghi dở

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix.rstrip("/"))
        if path.is_dir():
            await asyncio.to_thread(shutil.rmtree, path)
        elif path.exists():
            await asyncio.to_thread(path.unlink)


def make_file_store(settings: Settings) -> FileStore:
    return LocalFileStore(settings.files_dir)  # FILE_STORE=s3 → S3FileStore khi foundations 3.3 xong
