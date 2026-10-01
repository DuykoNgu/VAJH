"""Provider giả, không gọi mạng, kết quả xác định - mặc định khi APP_ENV=test."""
import hashlib
import math
import random

from pydantic import BaseModel

from app.ai.embeddings import EMBEDDING_DIM
from app.ai.llm import LLMResult, Refusal, resolve_route
from app.ai.speech import Speech, SynthesizeRequest, TranscribeRequest, Transcript


class FakeLLM:
    """Trả lần lượt các câu trả lời đã `script(...)`; hết kịch bản thì lặp lại câu cuối của người dùng."""

    def __init__(self, settings):
        self.settings = settings
        self.scripted: list = []
        self.calls: list[dict] = []

    def script(self, *responses) -> "FakeLLM":
        """Mỗi phần tử: str (text), dict/BaseModel (structured output) hoặc Refusal."""
        self.scripted.extend(responses)
        return self

    def _next(self, route, messages, system, schema):
        resolve_route(self.settings, route)
        self.calls.append({"route": route, "messages": messages, "system": system, "schema": schema})
        reply = self.scripted.pop(0) if self.scripted else _last_user_text(messages)
        if isinstance(reply, Refusal):
            return reply
        if schema is not None:
            data = reply.model_dump() if isinstance(reply, BaseModel) else reply
            parsed = schema.model_validate(data)  # ValidationError nếu kịch bản sai schema
            return LLMResult(text=parsed.model_dump_json(), parsed=parsed, stop_reason="end_turn")
        return LLMResult(text=str(reply), stop_reason="end_turn")

    async def complete(self, route, messages, *, system=None, schema=None):
        return self._next(route, messages, system, schema)

    async def stream(self, route, messages, *, system=None):
        result = self._next(route, messages, system, None)
        if isinstance(result, LLMResult) and result.text:
            half = len(result.text) // 2 or len(result.text)
            for piece in (result.text[:half], result.text[half:]):
                if piece:
                    yield piece
        yield result


def _last_user_text(messages) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            content = m["content"]
            if isinstance(content, str):
                return content
            return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return ""


class FakeEmbeddings:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [fake_vector(t) for t in texts]


def fake_vector(text: str) -> list[float]:
    """Vector đơn vị 1536 chiều, cùng text → cùng vector."""
    rng = random.Random(hashlib.sha256(text.encode()).digest())
    v = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


class FakeSTT:
    """Test gửi text dưới dạng "audio": bytes được giải mã UTF-8 thành transcript."""

    async def transcribe(self, request: TranscribeRequest) -> Transcript:
        return Transcript(text=request.audio.decode("utf-8"), language=request.language)


class FakeTTS:
    async def synthesize(self, request: SynthesizeRequest) -> Speech:
        return Speech(audio=b"FAKEAUDIO:" + request.text.encode(), audio_format="audio/x-fake")
