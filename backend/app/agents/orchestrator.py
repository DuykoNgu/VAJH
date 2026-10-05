"""Orchestrator Agent: hiểu yêu cầu của học sinh và quyết định agent nào làm tiếp (structured output).

Lệnh ngắn rõ nghĩa ("tiếp", "kiểm tra mình") được nhận ra bằng từ khoá, không gọi LLM (đỡ ~3 s mỗi lượt học).
"""
import re
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


QUICK = {
    "next": {"tiếp", "tiếp đi", "tiếp tục", "tiếp theo", "học tiếp", "giảng tiếp", "đi tiếp", "sang ý sau",
             "ý tiếp", "ý tiếp theo", "ý sau", "phần tiếp", "phần tiếp theo", "phần sau", "sang phần sau"},
    "quiz": {"kiểm tra", "kiểm tra mình", "kiểm tra đi", "kiểm tra em", "làm bài kiểm tra", "làm kiểm tra"},
}
POLITE = re.compile(r"\b(nhé|nha|ạ|à|ơi|lusia|đi ạ|giúp mình|giúp em)\b")


def quick_intent(text: str | None) -> str | None:
    """"Tiếp nhé." → next, "Kiểm tra mình đi ạ" → quiz; câu khác → None (để LLM hiểu)."""
    words = re.sub(r"[^\w\s]", " ", (text or "").lower())
    words = " ".join(POLITE.sub(" ", words).split())
    return next((intent for intent, phrases in QUICK.items() if words in phrases), None)


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
        if intent := quick_intent(ctx.text):  # lệnh ngắn: quyết định ngay, không gọi LLM
            target = "assessment" if intent == "quiz" else "knowledge"
            yield AgentResult(self.name, "", handoff=Handoff(target, intent,
                                                             {"intent": intent, "query": ctx.text or "", "quick": True}))
            return
        messages = history_messages(ctx) + [{"role": "user", "content": ctx.text or ""}]
        result = await self.llm.complete("orchestrator", messages, system=SYSTEM, schema=Route)
        if isinstance(result, Refusal):
            yield AgentResult(self.name, "", refusal=result.category or "refused")
            return
        route: Route = result.parsed
        target = "assessment" if route.intent == "quiz" else "knowledge"
        yield AgentResult(self.name, "", handoff=Handoff(target, route.intent,
                                                         {"intent": route.intent, "query": route.query or ctx.text}))
