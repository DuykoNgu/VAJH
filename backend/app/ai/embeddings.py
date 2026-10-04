"""Embedding: mỗi đoạn text → vector 1024 chiều (khớp cột chunks.embedding vector(1024))."""
import asyncio
from functools import lru_cache
from typing import Protocol

from app.config import Settings

# Phải khớp migrations/002_embedding_1024.sql (chunks.embedding vector(1024)); đổi model = migration mới + embed lại
EMBEDDING_DIM = 1024
# Model huấn luyện với passage tối đa 2048 token (mặc định của repo là 8192, tốn RAM vô ích)
MAX_SEQ_LENGTH = 2048
BATCH_SIZE = 32


class EmbeddingDimensionError(ValueError):
    pass


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def check_dimensions(vectors: list[list[float]]) -> list[list[float]]:
    for v in vectors:
        if len(v) != EMBEDDING_DIM:
            raise EmbeddingDimensionError(f"expected {EMBEDDING_DIM}-dimension embeddings, got {len(v)}")
    return vectors


@lru_cache
def load_model(name: str):
    # Import muộn: test dùng provider fake không cần cài torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(name)
    model.max_seq_length = MAX_SEQ_LENGTH
    return model


class LocalEmbeddings:
    """Chạy model trong tiến trình (CPU/MPS/CUDA tự chọn); vector đã chuẩn hóa nên cosine = dot product."""

    def __init__(self, settings: Settings, model=None):
        self.name = settings.embedding_model
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self.model or load_model(self.name)  # tải lần đầu khi cần (~2.3GB)
        # ponytail: encode chặn CPU nên đẩy sang thread; tách thành embedding server khi API bị nghẽn
        arr = await asyncio.to_thread(model.encode, texts, batch_size=BATCH_SIZE, normalize_embeddings=True)
        return check_dimensions([v.tolist() for v in arr])


async def warm_up(embeddings: EmbeddingClient) -> None:
    """Nạp model (~2 GB) lúc khởi động thay vì ở câu hỏi đầu tiên của học sinh."""
    try:
        await embeddings.embed(["khởi động"])
    except Exception as e:  # noqa: BLE001 - API vẫn chạy; lỗi sẽ hiện ở lần tìm kiếm thật
        import sys

        print(f"embedding warm-up skipped: {e}", file=sys.stderr)


def make_embeddings(settings: Settings) -> EmbeddingClient:
    if settings.embedding_provider == "fake":
        from app.ai.fakes import FakeEmbeddings

        return FakeEmbeddings()
    return LocalEmbeddings(settings)
