"""Learning / Tutor Agent: giảng bài bằng lời, gợi mở, chỉ dựa trên đoạn SGK được chuyển tới."""
from pydantic import BaseModel

from app.agents.base import AgentResult, Handoff, TurnContext
from app.agents.orchestrator import history_messages
from app.ai.llm import LLMClient, Refusal

NOT_FOUND = "Mình không tìm thấy điều này trong sách giáo khoa."
REFUSED = "Xin lỗi, mình không trả lời được câu này. Em hỏi mình về bài học nhé."


# Phong cách cho người học bằng tai: đi thẳng vào kiến thức, câu ngắn; hình ảnh chỉ khi khó hình dung và phải cụ thể
LISTENING_STYLE = (
    "Học sinh chỉ NGHE, không nhìn màn hình. Mỗi câu NGẮN (dưới 15 từ) và chỉ một ý. ĐI THẲNG VÀO KIẾN THỨC: câu đầu nêu "
    "ngay điều cần nhớ (định nghĩa, quy tắc, kết quả) đúng như sách; không mở đầu bằng chuyện chương, mục tiêu hay lời "
    "dẫn dài. Hình ảnh so sánh chỉ dùng khi điều đó khó hình dung (hình học, đồ thị, vị trí) và phải cụ thể, gắn với số "
    "liệu của bài (ví dụ: trục số như cây thước nằm ngang, số dương ở bên phải); không dùng ẩn dụ chung chung. Nói vị "
    "trí theo cơ thể và hướng (trái, phải, lên, xuống). KHÔNG bao giờ nói 'nhìn', 'quan sát', 'như hình vẽ'. Không dùng "
    "ký hiệu toán: viết 'y bằng hai x cộng một', 'x mũ ba'."
)


def system_prompt(grade: int | None) -> str:
    return (
        f"Bạn là LUSIA, gia sư kiên nhẫn cho học sinh khiếm thị lớp {grade or 8}. {LISTENING_STYLE} Trả lời 2 đến 4 câu, "
        "câu đầu trả lời thẳng điều em hỏi. CHỈ dùng các đoạn sách được đánh số và lịch sử hội thoại; không bịa. Khi giảng "
        "bài, có thể kết thúc bằng MỘT câu hỏi ngắn có đáp án rõ ràng. Nếu các đoạn sách không liên quan đến câu hỏi, trả "
        f"lời đúng câu: \"{NOT_FOUND}\" và để `cited` rỗng. `cited` là số thứ tự các đoạn đã dùng; KHÔNG ghi số đoạn "
        "như [1] vào câu trả lời."
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
        f"Bạn là LUSIA, gia sư kiên nhẫn cho học sinh khiếm thị lớp {grade or 8}, đang giảng MỘT ý của bài. "
        f"{LISTENING_STYLE} `explanation`: 2 đến 4 câu ngắn: câu 1 nêu thẳng kiến thức của ý này; câu 2 và 3 đọc MỘT ví "
        "dụ cụ thể trong sách (số, biểu thức) và cách làm; chỉ thêm một câu hình ảnh nếu thật cần. Không nhắc lại tên bài, "
        "không nói 'trong phần này', 'chương này', không mở rộng ra ngoài ý này. CHỈ dựa trên đoạn sách được đánh số; nếu "
        "có MÔ TẢ HÌNH thì nói dữ kiện của hình theo thứ tự (trục, hướng, điểm đặc biệt). `check_question`: MỘT câu hỏi "
        "ngắn về đúng ý vừa giảng, có đáp án rõ ràng, trả lời được bằng vài từ (không hỏi chung chung kiểu 'có gì giống "
        "nhau'). `expected_answer`: đáp án. Không ghi số đoạn như [1] vào lời giảng."
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
