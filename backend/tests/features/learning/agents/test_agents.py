import uuid

from app.config import get_settings
from app.core.ai.fakes import FakeLLM
from app.core.ai.llm import Refusal
from app.core.rag.retrieval import Evidence
from app.features.learning.agents.base import TurnContext
from app.features.learning.agents.knowledge import KnowledgeAgent
from app.features.learning.agents.orchestrator import OrchestratorAgent
from app.features.learning.agents.tutor import REFUSED, TutorAgent
from app.features.learning.agents.vision import VisionAgent
from app.features.learning.service import final

CTX = TurnContext(mode="chat", session_id=uuid.uuid4(), student_id=uuid.uuid4(), grade=8, text="câu hỏi")
TEXT = Evidence(1, "text", 4, "Đồ thị là đường thẳng.", lesson_title="Bài 2")
FIG = Evidence(2, "figure", 5, "Mô tả hình", review="pending", lesson_title="Bài 2")


def llm(*replies):
    return FakeLLM(get_settings()).script(*replies)


async def test_orchestrator_routes_quiz_to_assessment_and_rest_to_knowledge():
    quiz = await final(OrchestratorAgent(llm({"intent": "quiz", "query": "kiểm tra"})), CTX)
    explain = await final(OrchestratorAgent(llm({"intent": "explain", "query": "q"})), CTX)
    assert quiz.handoff.target == "assessment" and explain.handoff.target == "knowledge"
    assert explain.handoff.payload == {"intent": "explain", "query": "q"}
    refused = await final(OrchestratorAgent(llm(Refusal("other"))), CTX)
    assert refused.refusal and refused.handoff is None


class StubEmbeddings:
    pass


async def test_knowledge_hands_off_to_vision_only_when_figure_in_top(monkeypatch):
    import app.features.learning.agents.knowledge as knowledge

    async def search(_emb, _q, _lesson, _k, results=()):
        return list(results)

    monkeypatch.setattr(knowledge, "search_knowledge", lambda *a: search(*a, results=[TEXT, FIG]))
    assert (await final(KnowledgeAgent(StubEmbeddings(), top_k=6), CTX)).handoff.target == "vision"
    monkeypatch.setattr(knowledge, "search_knowledge", lambda *a: search(*a, results=[TEXT]))
    result = await final(KnowledgeAgent(StubEmbeddings(), top_k=6), CTX)
    assert result.handoff.target == "tutor" and result.handoff.payload["evidence"] == [TEXT]


async def test_vision_puts_the_figure_first():
    from dataclasses import replace

    result = await final(VisionAgent(), replace(CTX, evidence=(TEXT, FIG)))
    assert result.handoff.payload["evidence"][0] == FIG and result.handoff.payload["figure"] == FIG
    assert "chưa duyệt" in result.handoff.reason


async def test_tutor_maps_citations_and_handles_refusal():
    from dataclasses import replace

    ctx = replace(CTX, evidence=(FIG, TEXT))
    result = await final(TutorAgent(llm({"answer": "Trả lời.", "cited": [2, 9]})), ctx)
    assert result.citations == (1,) and result.speech_text == "Trả lời."
    refused = await final(TutorAgent(llm(Refusal("other"))), ctx)
    assert refused.speech_text == REFUSED and refused.refusal
