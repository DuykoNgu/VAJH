import json

import httpx2
import openai
import pytest

from app.ai.embeddings import EmbeddingDimensionError, OpenAIEmbeddings
from app.config import get_settings


def embeddings_with(dim, calls):
    def handler(request):
        inputs = json.loads(request.content)["input"]
        calls.append(len(inputs))
        # trả ngược thứ tự để kiểm tra client sắp xếp lại theo index
        data = [{"object": "embedding", "index": i, "embedding": [float(i)] * dim} for i in range(len(inputs))][::-1]
        return httpx2.Response(200, json={"object": "list", "data": data, "model": "m",
                                          "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    client = openai.AsyncOpenAI(api_key="k", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    return OpenAIEmbeddings(get_settings(), client=client)


async def test_batch_returns_one_vector_per_text_in_order():
    calls = []
    vectors = await embeddings_with(1536, calls).embed(["a", "b", "c"])
    assert [len(v) for v in vectors] == [1536] * 3
    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert calls == [3]


async def test_large_input_is_split_into_batches():
    calls = []
    vectors = await embeddings_with(1536, calls).embed([str(i) for i in range(300)])
    assert len(vectors) == 300 and calls == [256, 44]


async def test_wrong_dimension_fails_with_expected_and_actual():
    with pytest.raises(EmbeddingDimensionError, match="1536.*768"):
        await embeddings_with(768, []).embed(["a"])
