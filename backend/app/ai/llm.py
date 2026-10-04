"""LLM client: mọi lời gọi LLM đều đi qua một "route" (agent) → model + effort trong cấu hình.

Provider chọn bằng LLM_PROVIDER: openai (mặc định, Responses API), anthropic, fake (test).
Tin nhắn dùng một dạng chung (role + text hoặc block, ảnh qua image_block); mỗi adapter tự chuyển đổi.

- Structured output: truyền `schema` (Pydantic model) → kết quả đã được kiểm tra theo schema.
- Streaming: `stream()` trả từng đoạn text rồi đúng một kết quả cuối (LLMResult hoặc Refusal).
- Từ chối (refusal): trả về `Refusal`, không bao giờ trả text như một câu trả lời.
- Retry lỗi tạm thời (429/5xx/mạng) do SDK tự làm; lỗi request/khóa API không retry.
"""
import base64
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from app.config import Route, Settings

log = logging.getLogger("lusia.llm")

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
STREAM_MAX_TOKENS = 64000


class UnknownRouteError(ValueError):
    pass


@dataclass
class LLMResult:
    text: str
    parsed: Any = None
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)


@dataclass
class Refusal:
    category: str | None = None
    explanation: str | None = None


class LLMClient(Protocol):
    async def complete(self, route: str, messages: list[dict], *, system: str | None = None,
                       schema: type[BaseModel] | None = None) -> LLMResult | Refusal: ...

    def stream(self, route: str, messages: list[dict], *,
               system: str | None = None) -> AsyncIterator["str | LLMResult | Refusal"]: ...


def image_block(data: bytes, media_type: str) -> dict:
    """Ảnh gửi kèm tin nhắn (base64 - URL MinIO local không truy cập được từ provider)."""
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(data).decode()}}


def resolve_route(settings: Settings, route: str) -> Route:
    try:
        cfg = settings.llm_routes[route]
    except KeyError:
        raise UnknownRouteError(f"unknown LLM route: {route!r}") from None
    if not cfg.model:
        raise UnknownRouteError(f"no model configured for LLM route {route!r}: set OPENAI_LLM_MODEL (or LLM_ROUTES)")
    return cfg


def _log(route: str, cfg: Route, started: float, outcome: str, usage: dict) -> None:
    log.info("llm call", extra={
        "route": route, "model": cfg.model, "effort": cfg.effort,
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "latency_ms": round((time.perf_counter() - started) * 1000), "outcome": outcome,
    })


def _usage(message) -> dict:
    u = getattr(message, "usage", None)
    return {"input_tokens": getattr(u, "input_tokens", None), "output_tokens": getattr(u, "output_tokens", None)}


def _refusal(message) -> Refusal | None:
    if message.stop_reason != "refusal":
        return None
    details = getattr(message, "stop_details", None)
    return Refusal(getattr(details, "category", None), getattr(details, "explanation", None))


def _text(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text")


class AnthropicLLM:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self._client = client

    @property
    def client(self):
        # Tạo khi gọi lần đầu: thiếu key thì lỗi lúc gọi LLM, không chặn API khởi động
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self.settings.anthropic_api_key,
                                                   timeout=self.settings.llm_timeout_s)
        return self._client

    def _params(self, cfg: Route, messages, system, max_tokens) -> dict:
        params = dict(model=cfg.model, max_tokens=max_tokens, messages=messages,
                      output_config={"effort": cfg.effort},
                      betas=[FALLBACK_BETA], fallbacks="default")
        if system:
            params["system"] = system
        return params

    async def complete(self, route, messages, *, system=None, schema=None):
        cfg = resolve_route(self.settings, route)  # route sai → lỗi trước khi gọi provider
        params = self._params(cfg, messages, system, MAX_TOKENS)
        started = time.perf_counter()
        try:
            if schema is not None:
                message = await self.client.beta.messages.parse(output_format=schema, **params)
            else:
                message = await self.client.beta.messages.create(**params)
        except Exception:
            _log(route, cfg, started, "error", {})
            raise
        usage = _usage(message)
        refusal = _refusal(message)
        _log(route, cfg, started, "refusal" if refusal else "ok", usage)
        if refusal:
            return refusal
        parsed = message.parsed_output if schema is not None else None
        if schema is not None and parsed is None:
            parsed = schema.model_validate_json(_text(message))  # ValidationError nếu sai schema
        return LLMResult(text=_text(message), parsed=parsed, stop_reason=message.stop_reason, usage=usage)

    async def stream(self, route, messages, *, system=None):
        cfg = resolve_route(self.settings, route)
        params = self._params(cfg, messages, system, STREAM_MAX_TOKENS)
        started = time.perf_counter()
        try:
            async with self.client.beta.messages.stream(**params) as s:
                async for text in s.text_stream:
                    yield text
                message = await s.get_final_message()
        except Exception:
            _log(route, cfg, started, "error", {})
            raise
        usage = _usage(message)
        refusal = _refusal(message)
        _log(route, cfg, started, "refusal" if refusal else "ok", usage)
        # Refusal giữa chừng: người gọi phải bỏ các đoạn text đã nhận
        yield refusal or LLMResult(text=_text(message), stop_reason=message.stop_reason, usage=usage)


class OpenAILLM:
    """OpenAI Responses API: parse() cho structured output, create() cho text, stream() cho streaming."""

    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self._client = client

    @property
    def client(self):
        # Tạo khi gọi lần đầu: thiếu key thì lỗi lúc gọi LLM, không chặn API khởi động
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.llm_timeout_s)
        return self._client

    @staticmethod
    def _input(messages: list[dict]) -> list[dict]:
        converted = []
        for m in messages:
            content = m["content"]
            if not isinstance(content, str):
                parts = []
                for block in content:
                    if block["type"] == "text":
                        parts.append({"type": "input_text" if m["role"] == "user" else "output_text",
                                      "text": block["text"]})
                    elif block["type"] == "image":
                        src = block["source"]
                        parts.append({"type": "input_image",
                                      "image_url": f"data:{src['media_type']};base64,{src['data']}"})
                content = parts
            converted.append({"role": m["role"], "content": content})
        return converted

    def _params(self, cfg: Route, messages, system, max_tokens) -> dict:
        params = dict(model=cfg.model, input=self._input(messages), max_output_tokens=max_tokens,
                      reasoning={"effort": cfg.effort})
        if system:
            params["instructions"] = system
        return params

    @staticmethod
    def _usage(response) -> dict:
        u = getattr(response, "usage", None)
        return {"input_tokens": getattr(u, "input_tokens", None), "output_tokens": getattr(u, "output_tokens", None)}

    @staticmethod
    def _refusal(response) -> Refusal | None:
        for item in response.output or []:
            for part in getattr(item, "content", None) or []:
                if part.type == "refusal":
                    return Refusal(category=None, explanation=part.refusal)
        return None

    async def complete(self, route, messages, *, system=None, schema=None):
        cfg = resolve_route(self.settings, route)
        params = self._params(cfg, messages, system, MAX_TOKENS)
        started = time.perf_counter()
        try:
            if schema is not None:
                response = await self.client.responses.parse(text_format=schema, **params)
            else:
                response = await self.client.responses.create(**params)
        except Exception:
            _log(route, cfg, started, "error", {})
            raise
        usage = self._usage(response)
        refusal = self._refusal(response)
        _log(route, cfg, started, "refusal" if refusal else "ok", usage)
        if refusal:
            return refusal
        parsed = None
        if schema is not None:
            parsed = response.output_parsed
            if parsed is None:
                parsed = schema.model_validate_json(response.output_text)  # ValidationError nếu sai schema
        return LLMResult(text=response.output_text, parsed=parsed, stop_reason=response.status, usage=usage)

    async def stream(self, route, messages, *, system=None):
        cfg = resolve_route(self.settings, route)
        params = self._params(cfg, messages, system, STREAM_MAX_TOKENS)
        started = time.perf_counter()
        try:
            async with self.client.responses.stream(**params) as s:
                async for event in s:
                    if event.type == "response.output_text.delta":
                        yield event.delta
                response = await s.get_final_response()
        except Exception:
            _log(route, cfg, started, "error", {})
            raise
        usage = self._usage(response)
        refusal = self._refusal(response)
        _log(route, cfg, started, "refusal" if refusal else "ok", usage)
        yield refusal or LLMResult(text=response.output_text, stop_reason=response.status, usage=usage)


def make_llm(settings: Settings) -> LLMClient:
    from app.tracing import TracingLLM  # mọi lượt gọi LLM thành span trong trace hiện tại (trang /monitor)

    if settings.llm_provider == "fake":
        from app.ai.fakes import FakeLLM

        return TracingLLM(FakeLLM(settings), settings)
    if settings.llm_provider == "anthropic":
        return TracingLLM(AnthropicLLM(settings), settings)
    return TracingLLM(OpenAILLM(settings), settings)
