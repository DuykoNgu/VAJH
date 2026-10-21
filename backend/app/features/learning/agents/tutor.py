"""Learning / Tutor Agent: giảng bài bằng lời, gợi mở, chỉ dựa trên đoạn SGK được chuyển tới."""
from pydantic import BaseModel

from app.core.ai.llm import LLMClient, Refusal
from app.features.learning.agents.base import AgentResult, Handoff, TurnContext
from app.features.learning.agents.orchestrator import history_messages
from app.prompts.learning import (
    tutor_answer_system,
    tutor_answer_user,
    tutor_teach_system,
    tutor_teach_user,
)

NOT_FOUND = "Mình không tìm thấy điều này trong sách giáo khoa."
REFUSED = "Xin lỗi, mình không trả lời được câu này. Em hỏi mình về bài học nhé."


class TutorAnswer(BaseModel):
    answer: str
    cited: list[int]


class TeachPart(BaseModel):
    hook: str = ""  # chỉ phần 1: câu dẫn vào bài
    explanation: str
    check_question: str
    expected_answer: str


class TutorAgent:
    name = "tutor"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, ctx: TurnContext):
        if ctx.mode == "teach":
            async for event in self._teach(ctx):
                yield event
            return
        messages = history_messages(ctx) + [{"role": "user", "content": tutor_answer_user(ctx.evidence, ctx.text)}]
        result = await self.llm.complete("tutor", messages, system=tutor_answer_system(ctx.grade, NOT_FOUND),
                                         schema=TutorAnswer)
        if isinstance(result, Refusal):
            yield AgentResult(self.name, REFUSED, refusal=result.category or "refused")
            return
        answer: TutorAnswer = result.parsed
        cited = tuple(ctx.evidence[i - 1].chunk_id for i in answer.cited if 1 <= i <= len(ctx.evidence))
        yield AgentResult(self.name, answer.answer.strip(), citations=cited)

    async def _teach(self, ctx: TurnContext):
        messages = history_messages(ctx) + [{"role": "user", "content": tutor_teach_user(ctx.evidence, ctx.text)}]
        result = await self.llm.complete("tutor", messages, system=tutor_teach_system(ctx.grade), schema=TeachPart)
        if isinstance(result, Refusal):
            yield AgentResult(self.name, REFUSED, refusal=result.category or "refused")
            return
        part: TeachPart = result.parsed
        # Câu hỏi kiểm tra chuyển cho Assessment chấm ở lượt sau; câu dẫn (chỉ phần mở đầu) đi kèm trong payload
        yield AgentResult(self.name, f"{part.explanation.strip()} {part.check_question.strip()}",
                          citations=tuple(e.chunk_id for e in ctx.evidence),
                          handoff=Handoff("assessment", "câu hỏi kiểm tra",
                                          {"question": part.check_question.strip(),
                                           "expected": part.expected_answer.strip(), "hook": part.hook.strip()}))
