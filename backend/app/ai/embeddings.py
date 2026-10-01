"""Embedding: mỗi đoạn text → vector 1536 chiều (khớp cột chunks.embedding vector(1536))."""
from typing import Protocol

from app.config import Settings

# Phải khớp migrations/000_init.sql (chunks.embedding vector(1536)); đổi model = migration mới + embed lại
EMBEDDING_DIM = 1536
BATCH_SIZE = 256


class EmbeddingDimensionError(ValueError):
    pass


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def check_dimensions(vectors: list[list[float]]) -> list[list[float]]:
    for v in vectors:
        if len(v) != EMBEDDING_DIM:
            raise EmbeddingDimensionError(f"expected {EMBEDDING_DIM}-dimension embeddings, got {len(v)}")
    return vectors


class OpenAIEmbeddings:
    def __init__(self, settings: Settings, client=None):
        import openai

        self.model = settings.embedding_model
        self.client = client or openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            resp = await self.client.embeddings.create(model=self.model, input=texts[i:i + BATCH_SIZE])
            vectors += [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        return check_dimensions(vectors)


def make_embeddings(settings: Settings) -> EmbeddingClient:
    if settings.embedding_provider == "fake":
        from app.ai.fakes import FakeEmbeddings

        return FakeEmbeddings()
    return OpenAIEmbeddings(settings)
