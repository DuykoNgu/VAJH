"""Vision Agent: đưa mô tả hình (đã viết lúc nạp SGK, giáo viên duyệt) vào câu trả lời; không gọi LLM."""
from app.agents.base import AgentResult, Handoff, TurnContext


class VisionAgent:
    name = "vision"

    async def run(self, ctx: TurnContext):
        figures = [e for e in ctx.evidence if e.kind == "figure"]
        if not figures:
            yield AgentResult(self.name, "", handoff=Handoff("tutor", "không có hình", {"evidence": ctx.evidence}))
            return
        figure = figures[0]
        # Hình lên đầu để Tutor ưu tiên mô tả hình
        ordered = (figure,) + tuple(e for e in ctx.evidence if e.chunk_id != figure.chunk_id)
        status = "chưa duyệt" if figure.unreviewed else "đã duyệt"
        yield AgentResult(self.name, "", citations=(figure.chunk_id,),
                          handoff=Handoff("tutor", f"mô tả hình trang {figure.page} ({status})",
                                          {"evidence": ordered, "figure": figure}))
