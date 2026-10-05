import json
import logging

import httpx2 as httpx
import openai
import pytest
from pydantic import BaseModel, ValidationError

from app.ai.llm import LLMResult, OpenAILLM, Refusal, UnknownRouteError, image_block, make_llm
from app.config import default_routes, get_settings

USER = [{"role": "user", "content": "Giải thích đồ thị y = 2x + 1"}]
MODEL = "test-openai-model"


def response(content, status="completed"):
    return {"id": "resp_1", "object": "response", "created_at": 1, "status": status, "model": MODEL,
            "output": [{"type": "message", "id": "msg_1", "status": "completed", "role": "assistant",
                        "content": content}],
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
            "parallel_tool_calls": True, "tool_choice": "auto", "tools": [], "error": None,
            "incomplete_details": None, "instructions": None, "metadata": {}}


def text(t):
    return response([{"type": "output_text", "text": t, "annotations": []}])


class Provider:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, request):
        self.requests.append(request)
        return self.responses.pop(0)

    def body(self, i=0):
        return json.loads(self.requests[i].content)


def ok(body):
    return httpx.Response(200, json=body)


def llm_with(provider, **update):
    settings = get_settings().model_copy(update={"llm_routes": default_routes("openai", MODEL), **update})
    client = openai.AsyncOpenAI(api_key="sk-test-secret", max_retries=2,
                                http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    return OpenAILLM(settings, client=client)


class Routing(BaseModel):
    intent: str
    target_agents: list[str]


def test_make_llm_selects_openai():
    s = get_settings().model_copy(update={"llm_provider": "openai", "openai_api_key": "k"})
    assert isinstance(make_llm(s).inner, OpenAILLM)


async def test_route_without_model_fails_before_request():
    provider = Provider()
    llm = llm_with(provider, llm_routes=default_routes("openai", None))
    with pytest.raises(UnknownRouteError, match="OPENAI_LLM_MODEL"):
        await llm.complete("tutor", USER)
    assert provider.requests == []


async def test_unknown_route_fails_before_request():
    provider = Provider()
    with pytest.raises(UnknownRouteError, match="teacher_bot"):
        await llm_with(provider).complete("teacher_bot", USER)
    assert provider.requests == []


async def test_plain_call_sends_model_effort_system_and_images():
    provider = Provider(ok(text("xin chào")))
    msgs = [{"role": "user", "content": [image_block(b"\x89PNG", "image/png"), {"type": "text", "text": "Hình gì?"}]},
            {"role": "assistant", "content": "Đây là đồ thị."}, {"role": "user", "content": "Vì sao?"}]
    result = await llm_with(provider).complete("orchestrator", msgs, system="Bạn là LUSIA")
    assert isinstance(result, LLMResult) and result.text == "xin chào"
    body = provider.body()
    assert body["model"] == MODEL and body["reasoning"] == {"effort": "low"}
    assert body["instructions"] == "Bạn là LUSIA"
    assert body["input"][0]["content"][0] == {"type": "input_image", "image_url": "data:image/png;base64,iVBORw=="}
    assert body["input"][0]["content"][1] == {"type": "input_text", "text": "Hình gì?"}
    assert body["input"][1] == {"role": "assistant", "content": "Đây là đồ thị."}


async def test_structured_output_is_parsed():
    provider = Provider(ok(text('{"intent": "explain_figure", "target_agents": ["knowledge", "vision"]}')))
    result = await llm_with(provider).complete("orchestrator", USER, schema=Routing)
    assert result.parsed == Routing(intent="explain_figure", target_agents=["knowledge", "vision"])
    assert provider.body()["text"]["format"]["type"] == "json_schema"


async def test_structured_output_not_matching_schema_fails():
    provider = Provider(ok(text('{"intent": 3}')))
    with pytest.raises(ValidationError):
        await llm_with(provider).complete("orchestrator", USER, schema=Routing)


async def test_refusal_is_reported_not_as_text():
    provider = Provider(ok(response([{"type": "refusal", "refusal": "Tôi không thể giúp việc này."}])))
    assert await llm_with(provider).complete("tutor", USER) == Refusal(None, "Tôi không thể giúp việc này.")


def sse(*events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps({**e, 'sequence_number': i})}\n\n"
                   for i, e in enumerate(events))


async def test_streaming_yields_fragments_then_final_result():
    started = response([], status="in_progress")
    started["output"] = []
    item = {"type": "message", "id": "msg_1", "status": "in_progress", "role": "assistant", "content": []}
    part = {"type": "output_text", "text": "", "annotations": []}
    body = sse(
        {"type": "response.created", "response": started},
        {"type": "response.output_item.added", "output_index": 0, "item": item},
        {"type": "response.content_part.added", "item_id": "msg_1", "output_index": 0, "content_index": 0,
         "part": part},
        {"type": "response.output_text.delta", "item_id": "msg_1", "output_index": 0, "content_index": 0,
         "delta": "Đây là ", "logprobs": []},
        {"type": "response.output_text.delta", "item_id": "msg_1", "output_index": 0, "content_index": 0,
         "delta": "đồ thị.", "logprobs": []},
        {"type": "response.output_text.done", "item_id": "msg_1", "output_index": 0, "content_index": 0,
         "text": "Đây là đồ thị.", "logprobs": []},
        {"type": "response.completed", "response": text("Đây là đồ thị.")},
    )
    provider = Provider(httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))
    events = [e async for e in llm_with(provider).stream("tutor", USER)]
    assert events[:2] == ["Đây là ", "đồ thị."]
    assert isinstance(events[2], LLMResult) and events[2].text == "Đây là đồ thị." and len(events) == 3


async def test_transient_error_is_retried():
    provider = Provider(httpx.Response(429, json={"error": {"message": "slow", "type": "rate_limit"}},
                                       headers={"retry-after-ms": "10"}), ok(text("xin chào")))
    assert (await llm_with(provider).complete("tutor", USER)).text == "xin chào"
    assert len(provider.requests) == 2


async def test_bad_request_is_not_retried():
    provider = Provider(httpx.Response(400, json={"error": {"message": "bad", "type": "invalid_request_error"}}))
    with pytest.raises(openai.BadRequestError):
        await llm_with(provider).complete("tutor", USER)
    assert len(provider.requests) == 1


async def test_one_usage_log_record_without_secrets(caplog):
    provider = Provider(ok(text("ok")))
    with caplog.at_level(logging.INFO, logger="lusia.llm"):
        await llm_with(provider).complete("tutor", USER)
    (r,) = [r for r in caplog.records if r.name == "lusia.llm"]
    assert (r.route, r.model, r.effort, r.input_tokens, r.output_tokens, r.outcome) == \
        ("tutor", MODEL, "low", 11, 7, "ok")
    dumped = json.dumps(r.__dict__, default=str)
    assert "sk-test-secret" not in dumped and "Giải thích" not in dumped
