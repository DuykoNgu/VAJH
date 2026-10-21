import numpy as np
import pytest

from app.config import get_settings
from app.core.rag.embeddings import EmbeddingDimensionError, LocalEmbeddings


class StubModel:
    """Thay SentenceTransformer: vector thứ i = [i, i, ...]."""

    def __init__(self, dim):
        self.dim = dim
        self.calls = []

    def encode(self, texts, batch_size, normalize_embeddings):
        self.calls.append((len(texts), normalize_embeddings))
        return np.array([[float(i)] * self.dim for i in range(len(texts))], dtype=np.float32)


async def test_batch_returns_one_vector_per_text_in_order():
    model = StubModel(1024)
    vectors = await LocalEmbeddings(get_settings(), model=model).embed(["a", "b", "c"])
    assert [len(v) for v in vectors] == [1024] * 3
    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert model.calls == [(3, True)]


async def test_wrong_dimension_fails_with_expected_and_actual():
    with pytest.raises(EmbeddingDimensionError, match="1024.*768"):
        await LocalEmbeddings(get_settings(), model=StubModel(768)).embed(["a"])


def test_default_model_is_vietnamese_embedding_v2():
    assert get_settings().embedding_model == "AITeamVN/Vietnamese_Embedding_v2"
