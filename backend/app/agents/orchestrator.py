"""Orchestrator Agent: hiểu yêu cầu của học sinh và quyết định agent nào làm tiếp (structured output)."""
from typing import Literal

from pydantic import BaseModel

from app.agents.base import AgentResult, Handoff, TurnContext
from app.ai.llm import LLMClient, Refusal

SYSTEM = (
    "Bạn là bộ điều phối của LUSIA, gia sư AI cho học sinh khiếm thị. Đọc câu mới nhất của học sinh (có thể kèm "
    "lịch sử) và phân loại:\n"
    "- figure: hỏi về hình, đồ thị, sơ đồ, biểu đồ, bản đồ, hình vẽ\n"
    "- quiz: muốn được kiểm tra, làm bài tập trắc nghiệm, ôn tập bằng câu hỏi\n"
    "- next: muốn học tiếp phần sau của bài ('tiếp', 'tiếp tục', 'giảng tiếp', 'hiểu rồi', 'sang phần sau')\n"
    "- explain: hỏi kiến thức, khái niệm, giải thích, hỏi tiếp về điều vừa học\n"
    "- other: chào hỏi, câu không liên quan đến bài học\n"
    "Viết lại `query` thành câu hỏi đầy đủ, tự hiểu được (thay 'nó', 'cái đó' bằng đối tượng trong lịch sử) để tìm "
    "trong sách giáo khoa."
)


class Route(BaseModel):
    intent: Literal["explain", "figure", "quiz", "next", "other"]
    query: str


def history_messages(ctx: TurnContext) -> list[dict]:
    return [{"role": "user" if m.role == "student" else "assistant", "content": m.content} for m in ctx.history]


class OrchestratorAgent:
    name = "orchestrator"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, ctx: TurnContext):
        messages = history_messages(ctx) + [{"role": "user", "content": ctx.text or ""}]
        result = await self.llm.complete("orchestrator", messages, system=SYSTEM, schema=Route)
        if isinstance(result, Refusal):
            yield AgentResult(self.name, "", refusal=result.category or "refused")
            return
        route: Route = result.parsed
        target = "assessment" if route.intent == "quiz" else "knowledge"
        yield AgentResult(self.name, "", handoff=Handoff(target, route.intent,
                                                         {"intent": route.intent, "query": route.query or ctx.text}))
