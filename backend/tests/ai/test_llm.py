import json
import logging

import anthropic
import httpx2 as httpx
import pytest
from pydantic import BaseModel, ValidationError

from app.ai.llm import AnthropicLLM, LLMResult, Refusal, UnknownRouteError, image_block
from app.config import Route, get_settings

USER = [{"role": "user", "content": "Giải thích đồ thị y = 2x + 1"}]


def message(text, stop_reason="end_turn", **extra):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 7}, **extra}


class Provider:
    """Giả lập API Anthropic qua httpx.MockTransport: ghi lại request, trả lần lượt các response."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    def body(self, i=0):
        return json.loads(self.requests[i].content)


def llm_with(provider, **settings_update):
    settings = get_settings().model_copy(update=settings_update)
    client = anthropic.AsyncAnthropic(api_key="sk-test-secret", max_retries=2,
                                      http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    return AnthropicLLM(settings, client=client)


def ok(body):
    return httpx.Response(200, json=body)


class Routing(BaseModel):
    intent: str
    target_agents: list[str]


async def test_unknown_route_fails_before_any_request():
    provider = Provider()
    with pytest.raises(UnknownRouteError, match="teacher_bot"):
        await llm_with(provider).complete("teacher_bot", USER)
    assert provider.requests == []


async def test_route_sets_model_effort_fallback_and_beta():
    provider = Provider(ok(message("ok")))
    routes = {**get_settings().llm_routes, "orchestrator": Route(model="other-model", effort="low")}
    await llm_with(provider, llm_routes=routes).complete("orchestrator", USER)
    body = provider.body()
    assert body["model"] == "other-model"
    assert body["output_config"]["effort"] == "low"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in provider.requests[0].headers["anthropic-beta"]


async def test_structured_output_is_parsed():
    provider = Provider(ok(message('{"intent": "explain_figure", "target_agents": ["knowledge", "vision"]}')))
    result = await llm_with(provider).complete("orchestrator", USER, schema=Routing)
    assert isinstance(result, LLMResult)
    assert result.parsed == Routing(intent="explain_figure", target_agents=["knowledge", "vision"])
    body = provider.body()
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "low"


async def test_structured_output_not_matching_schema_fails():
    provider = Provider(ok(message('{"intent": 3}')))
    with pytest.raises(ValidationError):
        await llm_with(provider).complete("orchestrator", USER, schema=Routing)


def sse(*events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


async def test_streaming_yields_fragments_then_final_result():
    start = message("")
    start["content"] = []
    start["stop_reason"] = None
    body = sse(
        {"type": "message_start", "message": start},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Đây là "}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "đồ thị."}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": {"output_tokens": 7}},
        {"type": "message_stop"},
    )
    provider = Provider(httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))
    events = [e async for e in llm_with(provider).stream("tutor", USER)]
    assert events[:2] == ["Đây là ", "đồ thị."]
    assert isinstance(events[2], LLMResult) and events[2].text == "Đây là đồ thị."
    assert len(events) == 3


async def test_refusal_is_reported_not_as_text():
    provider = Provider(ok(message("", stop_reason="refusal",
                                   stop_details={"type": "refusal", "category": "cyber", "explanation": "no"})))
    result = await llm_with(provider).complete("tutor", USER)
    assert result == Refusal(category="cyber", explanation="no")


async def test_transient_error_is_retried():
    provider = Provider(httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit_error",
                                                                               "message": "slow down"}},
                                       headers={"retry-after-ms": "10"}),
                        ok(message("xin chào")))
    result = await llm_with(provider).complete("tutor", USER)
    assert result.text == "xin chào" and len(provider.requests) == 2


async def test_bad_request_is_not_retried():
    provider = Provider(httpx.Response(400, json={"type": "error", "error": {"type": "invalid_request_error",
                                                                               "message": "bad"}}))
    with pytest.raises(anthropic.BadRequestError):
        await llm_with(provider).complete("tutor", USER)
    assert len(provider.requests) == 1


async def test_one_usage_log_record_without_secrets(caplog):
    provider = Provider(ok(message("ok")))
    with caplog.at_level(logging.INFO, logger="lusia.llm"):
        await llm_with(provider).complete("tutor", USER)
    records = [r for r in caplog.records if r.name == "lusia.llm"]
    assert len(records) == 1
    r = records[0]
    assert (r.route, r.model, r.effort, r.input_tokens, r.output_tokens, r.outcome) == \
        ("tutor", "claude-opus-5-5", "medium", 11, 7, "ok")
    assert isinstance(r.latency_ms, int)
    dumped = json.dumps(r.__dict__, default=str)
    assert "sk-test-secret" not in dumped and "Giải thích" not in dumped


def test_image_block_is_base64():
    block = image_block(b"\x89PNG", "image/png")
    assert block["source"] == {"type": "base64", "media_type": "image/png", "data": "iVBORw=="}
