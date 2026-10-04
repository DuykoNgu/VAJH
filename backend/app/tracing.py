"""Trace agent + LLM để debug và đánh giá (trang /monitor).

Mỗi lượt học / vào bài / nghe thử / nạp sách mở MỘT trace; bên trong là các span: agent (run_agent) và lượt gọi LLM
(TracingLLM), span LLM nằm dưới agent gọi nó. Trace và span giữ trong ContextVar (asyncio.gather kế thừa), ghi DB
một lần khi trace kết thúc; ghi lỗi chỉ log, không làm hỏng lượt học.
"""
import json
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.config import Settings, get_settings
from app.storage import relational

log = logging.getLogger("lusia.tracing")
CAP = 8000  # ký tự tối đa mỗi trường văn bản lưu lại
PAYLOAD_KEYS = ["system", "messages", "response", "input", "output"]  # nội dung (có lời học sinh); còn lại là số liệu


def cap(text: Any) -> str | None:
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= CAP else text[:CAP] + f"… [+{len(text) - CAP} ký tự]"


@dataclass
class Span:
    seq: int
    parent_seq: int | None
    kind: str  # agent | llm
    name: str
    started: float
    offset_ms: int
    duration_ms: int = 0
    status: str = "ok"  # ok | refusal | error
    model: str | None = None
    effort: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class Trace:
    id: UUID
    kind: str
    started: float
    started_at: datetime
    session_id: UUID | None = None
    document_id: UUID | None = None
    input: str | None = None
    output: str | None = None
    spans: list[Span] = field(default_factory=list)


_trace: ContextVar[Trace | None] = ContextVar("lusia_trace", default=None)
_span: ContextVar[int | None] = ContextVar("lusia_span", default=None)


def current() -> Trace | None:
    return _trace.get()


@asynccontextmanager
async def trace(kind: str, *, session_id: UUID | None = None, document_id: UUID | None = None,
                input: str | None = None):
    t = Trace(uuid.uuid4(), kind, time.perf_counter(), datetime.now(UTC), session_id, document_id, cap(input))
    previous = _trace.get(), _span.get()
    _trace.set(t)
    _span.set(None)
    try:
        yield t
    except Exception as e:
        _trace.set(previous[0])
        _span.set(previous[1])
        await _save(t, f"{type(e).__name__}: {e}")
        raise
    _trace.set(previous[0])
    _span.set(previous[1])
    await _save(t, None)


@contextmanager
def span(kind: str, name: str, **fields):
    """Span con của span hiện tại; không có trace thì không làm gì (yield None)."""
    t = _trace.get()
    if t is None:
        yield None
        return
    now = time.perf_counter()
    s = Span(len(t.spans), _span.get(), kind, name, now, round((now - t.started) * 1000), **fields)
    t.spans.append(s)
    previous = _span.get()
    _span.set(s.seq)  # set(previous) thay vì reset(token): agent là async generator, có thể đóng ở context khác
    try:
        yield s
    except Exception as e:
        s.status = "error"
        s.detail["error"] = cap(f"{type(e).__name__}: {e}")
        raise
    finally:
        s.duration_ms = round((time.perf_counter() - s.started) * 1000)
        _span.set(previous)


def _messages(messages: list[dict]) -> list[dict]:
    """Tin nhắn gửi LLM để lưu: ảnh thay bằng "[ảnh PNG 120 KB]", chữ cắt ngắn."""
    out = []
    for m in messages:
        content = m["content"]
        if not isinstance(content, str):
            parts = []
            for block in content:
                if block["type"] == "image":
                    size = len(block["source"]["data"]) * 3 // 4 // 1024
                    kind = block["source"]["media_type"].split("/")[-1].upper()
                    parts.append(f"[ảnh {kind} {size} KB]")
                else:
                    parts.append(block.get("text", ""))
            content = "\n".join(parts)
        out.append({"role": m["role"], "content": cap(content)})
    return out


class TracingLLM:
    """Bọc LLM client bất kỳ (kể cả FakeLLM): mỗi complete() là một span LLM. Thuộc tính khác chuyển thẳng xuống."""

    def __init__(self, inner, settings: Settings):
        self.inner = inner
        self.settings = settings

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def complete(self, route, messages, *, system=None, schema=None):
        cfg = self.settings.llm_routes.get(route)
        with span("llm", route, model=cfg.model if cfg else None, effort=cfg.effort if cfg else None) as s:
            if s is not None:
                s.detail.update(system=cap(system), messages=_messages(messages),
                                schema=schema.__name__ if schema else None)
            result = await self.inner.complete(route, messages, system=system, schema=schema)
            if s is not None:
                if hasattr(result, "text"):
                    s.input_tokens = result.usage.get("input_tokens")
                    s.output_tokens = result.usage.get("output_tokens")
                    s.detail["response"] = cap(result.text)
                else:  # Refusal
                    s.status = "refusal"
                    s.detail["refusal"] = cap(f"{result.category}: {result.explanation}")
        return result

    def stream(self, route, messages, *, system=None):
        # ponytail: stream chưa được agent nào dùng nên chưa trace; thêm span khi Tutor chuyển sang streaming
        return self.inner.stream(route, messages, system=system)


def _keep_payload(t: Trace, error: str | None, settings: Settings) -> bool:
    """Lỗi / LLM từ chối → luôn giữ đủ prompt để debug; còn lại lấy mẫu theo TRACE_SAMPLE_RATE."""
    if settings.trace_payloads == "all" or error or any(s.status != "ok" for s in t.spans):
        return True
    return random.random() < settings.trace_sample_rate


async def _save(t: Trace, error: str | None) -> None:
    duration = round((time.perf_counter() - t.started) * 1000)
    if not _keep_payload(t, error, get_settings()):
        for s in t.spans:  # chỉ giữ số liệu: thời gian, token, trạng thái, handoff, trích dẫn
            for key in PAYLOAD_KEYS:
                s.detail.pop(key, None)
            s.detail["payload"] = "omitted"
    try:
        async with relational.transaction() as conn:
            await conn.execute(
                "INSERT INTO traces (id, kind, session_id, document_id, started_at, duration_ms, status, error, input,"
                " output) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (t.id, t.kind, t.session_id, t.document_id, t.started_at, duration, "error" if error else "ok",
                 cap(error), t.input, cap(t.output)))
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO trace_spans (trace_id, seq, parent_seq, kind, name, offset_ms, duration_ms, status,"
                    " model, effort, input_tokens, output_tokens, detail)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [(t.id, s.seq, s.parent_seq, s.kind, s.name, s.offset_ms, s.duration_ms, s.status, s.model,
                      s.effort, s.input_tokens, s.output_tokens, json.dumps(s.detail, ensure_ascii=False, default=str))
                     for s in t.spans])
    except Exception as e:  # giám sát không bao giờ làm hỏng lượt học
        log.warning("trace not saved", extra={"trace_id": str(t.id), "error": str(e)})


async def purge(payload_days: int, keep_days: int) -> dict:
    """Xoá trace quá cũ; bỏ nội dung (prompt, lời học sinh) của trace chưa đánh giá quá `payload_days` ngày."""
    async with relational.transaction() as conn:
        deleted = (await conn.execute("DELETE FROM traces WHERE started_at < now() - make_interval(days => %s)",
                                      (keep_days,))).rowcount
        old = "t.started_at < now() - make_interval(days => %s) AND t.rating IS NULL"
        spans = (await conn.execute(
            f"UPDATE trace_spans s SET detail = (s.detail - %s::text[]) || '{{\"payload\": \"purged\"}}'"
            f" FROM traces t WHERE t.id = s.trace_id AND {old} AND s.detail ?| %s::text[]",
            (PAYLOAD_KEYS, payload_days, PAYLOAD_KEYS))).rowcount
        traces = (await conn.execute(
            f"UPDATE traces t SET input = NULL, output = NULL WHERE {old}"
            " AND (t.input IS NOT NULL OR t.output IS NOT NULL)", (payload_days,))).rowcount
    result = {"deleted_traces": deleted, "purged_spans": spans, "purged_traces": traces}
    log.info("traces purged", extra=result)
    return result
