import uuid
from types import SimpleNamespace

import pytest

from app.agents import base
from app.agents.base import (AGENT_NAMES, AgentContractError, AgentResult, Evidence, Handoff, Registry, StubAgent,
                             TextDelta, TurnContext, run_agent)
from tests.conftest import running_app

SESSION, STUDENT = uuid.uuid4(), uuid.uuid4()


def ctx(language="vi"):
    return TurnContext(mode="chat", session_id=SESSION, student_id=STUDENT, grade=8, language=language)


class Scripted:
    def __init__(self, name, *events):
        self.name, self.events = name, events

    async def run(self, ctx):
        for e in self.events:
            yield e


async def collect(agent, c=None):
    return [e async for e in run_agent(agent, c or ctx())]


async def test_fragments_match_final_answer():
    agent = Scripted("tutor", TextDelta("Đây là "), TextDelta("đồ thị."), AgentResult("tutor", "Đây là đồ thị."))
    events = await collect(agent)
    assert events[-1].speech_text == "Đây là đồ thị."


async def test_fragments_not_matching_final_is_error():
    agent = Scripted("tutor", TextDelta("Đây là "), AgentResult("tutor", "khác"))
    with pytest.raises(AgentContractError, match="does not match"):
        await collect(agent)


async def test_exactly_one_final_result():
    with pytest.raises(AgentContractError, match="after its final"):
        await collect(Scripted("tutor", AgentResult("tutor", "a"), AgentResult("tutor", "b")))
    with pytest.raises(AgentContractError, match="without a final"):
        await collect(Scripted("tutor", TextDelta("a")))


async def test_knowledge_hands_off_to_vision():
    handoff = Handoff("vision", "figure question", {"chunk_id": 42})
    events = await collect(Scripted("knowledge", AgentResult("knowledge", "", handoff=handoff)))
    assert events[-1].handoff == handoff


@pytest.mark.parametrize("target", ["teacher", "knowledge"])
async def test_invalid_handoff_target_rejected(target):
    with pytest.raises(AgentContractError, match=target):
        await collect(Scripted("knowledge", AgentResult("knowledge", "", handoff=Handoff(target, "x"))))


def test_ingestion_context_has_no_student():
    c = TurnContext.ingestion(object_key="fig/toan8-46.png")
    assert (c.mode, c.session_id, c.student_id, c.language, c.history) == ("ingestion", None, None, "vi", ())
    with pytest.raises(AgentContractError):
        TurnContext(mode="ingestion", student_id=STUDENT)
    with pytest.raises(AgentContractError):
        TurnContext(mode="chat")


def test_context_carries_the_students_language():
    user = SimpleNamespace(student_id=STUDENT, grade=8, language="ja", speech_rate=1.25)
    c = TurnContext.for_student(user, session_id=SESSION, text="質問")
    assert (c.language, c.student_id, c.speech_rate, c.mode) == ("ja", STUDENT, 1.25, "chat")


def test_duplicate_registration_rejected():
    r = Registry()
    r.register(StubAgent("tutor"))
    with pytest.raises(AgentContractError, match="tutor"):
        r.register(StubAgent("tutor"))


def test_default_registry_is_complete():
    base.registry.assert_complete()


async def test_startup_fails_when_an_agent_is_missing(monkeypatch):
    incomplete = Registry()
    for name in AGENT_NAMES:
        if name != "assessment":
            incomplete.register(StubAgent(name))
    monkeypatch.setattr(base, "registry", incomplete)
    with pytest.raises(AgentContractError, match="assessment"):
        async with running_app():
            pass


async def test_stub_answers_in_japanese():
    events = await collect(base.registry.get("vision"), ctx("ja"))
    assert events == [AgentResult("vision", base.NOT_AVAILABLE["ja"])]


def test_evidence_is_carried_in_context():
    ev = Evidence(42, "figure", 6, "Đồ thị đi lên", review="pending", lesson_title="Bài 2")
    c = TurnContext(mode="chat", session_id=SESSION, student_id=STUDENT, evidence=(ev,))
    assert c.evidence[0].unreviewed and c.evidence[0].page == 6
    assert ctx().evidence == ()
