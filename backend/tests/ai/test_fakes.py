import pytest
from pydantic import BaseModel, ValidationError

from app.ai.embeddings import make_embeddings
from app.ai.fakes import FakeEmbeddings, FakeLLM, FakeSTT, FakeTTS
from app.ai.llm import LLMResult, Refusal, UnknownRouteError, make_llm
from app.ai.speech import SynthesizeRequest, TranscribeRequest, make_stt, make_tts
from app.config import get_settings


class Routing(BaseModel):
    intent: str


def test_test_settings_select_fakes():
    s = get_settings()
    assert isinstance(make_llm(s), FakeLLM) and isinstance(make_embeddings(s), FakeEmbeddings)
    assert isinstance(make_stt(s), FakeSTT) and isinstance(make_tts(s), FakeTTS)


async def test_stable_fake_embedding():
    a, b = await FakeEmbeddings().embed(["Hàm số bậc nhất", "Hàm số bậc nhất"])
    assert a == b and len(a) == 1024
    (c,) = await FakeEmbeddings().embed(["khác"])
    assert c != a


async def test_fake_llm_scripted_echo_refusal_and_schema():
    llm = FakeLLM(get_settings()).script("xin chào", {"intent": "ask"}, Refusal("cyber"))
    user = [{"role": "user", "content": "câu hỏi"}]
    assert (await llm.complete("tutor", user)).text == "xin chào"
    assert (await llm.complete("orchestrator", user, schema=Routing)).parsed == Routing(intent="ask")
    assert await llm.complete("tutor", user) == Refusal("cyber")
    assert (await llm.complete("tutor", user)).text == "câu hỏi"  # hết kịch bản → echo
    assert [c["route"] for c in llm.calls] == ["tutor", "orchestrator", "tutor", "tutor"]


async def test_fake_llm_schema_mismatch_and_unknown_route():
    llm = FakeLLM(get_settings()).script({"intent": 3})
    with pytest.raises(ValidationError):
        await llm.complete("orchestrator", [{"role": "user", "content": "x"}], schema=Routing)
    with pytest.raises(UnknownRouteError):
        await llm.complete("nope", [])


async def test_fake_llm_stream_fragments_join_to_final():
    llm = FakeLLM(get_settings()).script("Đây là đồ thị.")
    events = [e async for e in llm.stream("tutor", [{"role": "user", "content": "x"}])]
    assert isinstance(events[-1], LLMResult)
    assert "".join(events[:-1]) == events[-1].text == "Đây là đồ thị."


async def test_fake_speech():
    t = await FakeSTT().transcribe(TranscribeRequest(audio="y bằng hai x".encode(), audio_format="x", language="vi"))
    assert t.text == "y bằng hai x"
    s = await FakeTTS().synthesize(SynthesizeRequest(text="chào", language="ja"))
    assert s.audio == "FAKEAUDIO:chào".encode()
