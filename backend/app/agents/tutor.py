"""Learning / Tutor Agent: giảng bài bằng lời, gợi mở, chỉ dựa trên đoạn SGK được chuyển tới."""
from pydantic import BaseModel

from app.agents.base import AgentResult, Handoff, TurnContext
from app.agents.orchestrator import history_messages
from app.ai.llm import LLMClient, Refusal

NOT_FOUND = "Mình không tìm thấy điều này trong sách giáo khoa."
REFUSED = "Xin lỗi, mình không trả lời được câu này. Em hỏi mình về bài học nhé."


# Phong cách cho người học bằng tai: câu ngắn, mỗi câu một ý, gợi hình ảnh bằng tưởng tượng và cảm giác cơ thể
LISTENING_STYLE = (
    "Học sinh chỉ NGHE, không nhìn màn hình. Mỗi câu NGẮN (dưới 15 từ) và chỉ một ý. Gợi hình ảnh trong đầu: mở đầu "
    "bằng 'Em hãy tưởng tượng…' khi giải thích; so sánh với thứ em có thể chạm, nghe, cảm nhận bằng cơ thể (cầu thang "
    "đi lên, sợi dây căng thẳng, mép bàn, bước chân sang phải, tiếng nhạc to dần); nói vị trí theo cơ thể và hướng "
    "(bên trái, bên phải, phía trên, phía dưới, đi lên, đi xuống). KHÔNG bao giờ nói 'nhìn', 'quan sát', 'như hình vẽ'. "
    "Không dùng ký hiệu toán: viết 'y bằng hai x cộng một'."
)


def system_prompt(grade: int | None) -> str:
    return (
        f"Bạn là LUSIA, gia sư kiên nhẫn cho học sinh khiếm thị lớp {grade or 8}. {LISTENING_STYLE} Trả lời 2 đến 4 câu. "
        "CHỈ dùng các đoạn sách được đánh số và lịch sử hội thoại; không bịa. Khi giảng bài, kết thúc bằng MỘT câu hỏi "
        f"gợi mở ngắn. Nếu các đoạn sách không liên quan đến câu hỏi, trả lời đúng câu: \"{NOT_FOUND}\" và để `cited` "
        "rỗng. `cited` là số thứ tự các đoạn đã dùng."
    )


class TutorAnswer(BaseModel):
    answer: str
    cited: list[int]


def evidence_block(ctx: TurnContext) -> str:
    if not ctx.evidence:
        return "(không có đoạn sách nào)"
    parts = []
    for i, e in enumerate(ctx.evidence, 1):
        label = "MÔ TẢ HÌNH" if e.kind == "figure" else "ĐOẠN SÁCH"
        parts.append(f"[{i}] {label} - {e.lesson_title or 'SGK'}, trang {e.page}:\n{e.content}")
    return "\n\n".join(parts)


def teach_prompt(grade: int | None) -> str:
    return (
        f"Bạn là LUSIA, gia sư kiên nhẫn cho học sinh khiếm thị lớp {grade or 8}, đang giảng MỘT ý nhỏ của bài. "
        f"{LISTENING_STYLE} `explanation`: 2 đến 4 câu ngắn, giúp em HÌNH DUNG ý này bằng tưởng tượng và cảm giác; nối "
        "với ý trước nếu có trong lịch sử. CHỈ dựa trên đoạn sách được đánh số; nếu là MÔ TẢ HÌNH thì dẫn em dựng hình "
        "đó trong đầu từng bước (trục, hướng, điểm đặc biệt). `check_question`: MỘT câu hỏi rất ngắn, trả lời được bằng "
        "vài từ. `expected_answer`: câu trả lời mong đợi."
    )


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
        messages = history_messages(ctx) + [{"role": "user", "content":
                                             f"Các đoạn sách:\n{evidence_block(ctx)}\n\nCâu hỏi của học sinh: {ctx.text}"}]
        result = await self.llm.complete("tutor", messages, system=system_prompt(ctx.grade), schema=TutorAnswer)
        if isinstance(result, Refusal):
            yield AgentResult(self.name, REFUSED, refusal=result.category or "refused")
            return
        answer: TutorAnswer = result.parsed
        cited = tuple(ctx.evidence[i - 1].chunk_id for i in answer.cited if 1 <= i <= len(ctx.evidence))
        yield AgentResult(self.name, answer.answer.strip(), citations=cited)

    async def _teach(self, ctx: TurnContext):
        messages = history_messages(ctx) + [{"role": "user", "content":
                                             f"Các đoạn sách:\n{evidence_block(ctx)}\n\n{ctx.text}"}]
        result = await self.llm.complete("tutor", messages, system=teach_prompt(ctx.grade), schema=TeachPart)
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
