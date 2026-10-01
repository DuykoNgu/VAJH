"""Hợp đồng chung của 7 agent LUSIA.

Một agent nhận TurnContext, phát ra 0..n TextDelta (đoạn text để đọc dần) rồi đúng MỘT AgentResult.
Người gọi luôn chạy agent qua run_agent() - hàm này kiểm tra hợp đồng thay vì tin từng agent.
Agent không bao giờ biết danh tính được xác định thế nào: chỉ nhận id/ngôn ngữ trong TurnContext.
"""
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

AgentName = Literal["orchestrator", "tutor", "knowledge", "vision", "document", "assessment", "student_model"]
AGENT_NAMES: tuple[str, ...] = AgentName.__args__
Mode = Literal["chat", "quiz", "ingestion"]


class AgentContractError(Exception):
    pass


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["student", "assistant"]
    content: str
    agent: str | None = None


@dataclass(frozen=True)
class TurnContext:
    mode: Mode
    language: Literal["vi", "ja"] = "vi"
    session_id: UUID | None = None
    student_id: UUID | None = None
    grade: int | None = None
    speech_rate: float = 1.0
    lesson_id: UUID | None = None
    text: str | None = None          # câu hỏi / nội dung đầu vào
    object_key: str | None = None    # ảnh hoặc tài liệu trong object storage
    history: tuple[ChatMessage, ...] = ()  # tin gần nhất, theo thứ tự thời gian

    def __post_init__(self):
        if self.mode == "ingestion":
            # Xử lý offline (nạp SGK, mô tả hình): không có phiên học, không có học sinh
            if self.session_id or self.student_id or self.history or self.language != "vi":
                raise AgentContractError("ingestion context must have no session, no student, no history, language vi")
        elif self.session_id is None or self.student_id is None:
            raise AgentContractError(f"{self.mode} context requires session_id and student_id")

    @classmethod
    def for_student(cls, user, *, session_id: UUID, mode: Mode = "chat", **kwargs) -> "TurnContext":
        """Copy thông tin học sinh từ UserContext (app.identity) - agent không thấy identity provider."""
        return cls(mode=mode, session_id=session_id, student_id=user.student_id, grade=user.grade,
                   language=user.language, speech_rate=user.speech_rate, **kwargs)

    @classmethod
    def ingestion(cls, **kwargs) -> "TurnContext":
        return cls(mode="ingestion", **kwargs)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Handoff:
    target: str
    reason: str
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    agent: str
    speech_text: str                          # câu trả lời để ĐỌC (ngôn ngữ của học sinh)
    citations: tuple[int, ...] = ()           # chunks.id đã dùng
    handoff: Handoff | None = None
    refusal: str | None = None                # category khi provider từ chối


class Agent(Protocol):
    name: str

    def run(self, ctx: TurnContext) -> AsyncIterator[TextDelta | AgentResult]: ...


async def run_agent(agent: Agent, ctx: TurnContext) -> AsyncIterator[TextDelta | AgentResult]:
    """Chạy agent và kiểm tra hợp đồng: text ghép lại == câu trả lời cuối, đúng 1 kết quả cuối, handoff hợp lệ."""
    fragments: list[str] = []
    final: AgentResult | None = None
    async for event in agent.run(ctx):
        if final is not None:
            raise AgentContractError(f"agent {agent.name} emitted events after its final result")
        if isinstance(event, TextDelta):
            fragments.append(event.text)
        elif isinstance(event, AgentResult):
            _check_result(agent, event, fragments)
            final = event
        else:
            raise AgentContractError(f"agent {agent.name} emitted unknown event {event!r}")
        yield event
    if final is None:
        raise AgentContractError(f"agent {agent.name} finished without a final result")


def _check_result(agent: Agent, result: AgentResult, fragments: list[str]) -> None:
    if result.agent != agent.name:
        raise AgentContractError(f"agent {agent.name} returned a result labelled {result.agent}")
    if fragments and "".join(fragments) != result.speech_text:
        raise AgentContractError(f"agent {agent.name}: streamed text does not match the final answer")
    h = result.handoff
    if h is not None and (h.target not in AGENT_NAMES or h.target == agent.name):
        raise AgentContractError(f"agent {agent.name}: invalid handoff target {h.target!r}")


class Registry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        if agent.name not in AGENT_NAMES:
            raise AgentContractError(f"unknown agent name {agent.name!r}")
        if agent.name in self._agents:
            raise AgentContractError(f"agent {agent.name!r} is already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        return self._agents[name]

    def assert_complete(self) -> None:
        missing = [n for n in AGENT_NAMES if n not in self._agents]
        if missing:
            raise AgentContractError(f"missing agent implementations: {', '.join(missing)}")


NOT_AVAILABLE = {
    "vi": "Xin lỗi, LUSIA chưa làm được việc này. Tính năng này đang được phát triển.",
    "ja": "申し訳ありません。この機能はまだ準備中です。",
}


class StubAgent:
    """Agent tạm (chưa có hành vi thật) - mỗi change sau thay đúng một dòng đăng ký bên dưới."""

    def __init__(self, name: str):
        self.name = name

    async def run(self, ctx: TurnContext):
        yield AgentResult(agent=self.name, speech_text=NOT_AVAILABLE[ctx.language])


registry = Registry()
registry.register(StubAgent("orchestrator"))
registry.register(StubAgent("tutor"))
registry.register(StubAgent("knowledge"))
registry.register(StubAgent("vision"))
registry.register(StubAgent("document"))
registry.register(StubAgent("assessment"))
registry.register(StubAgent("student_model"))
