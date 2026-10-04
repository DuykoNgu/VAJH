"""RAG / Knowledge Agent: tìm đoạn SGK liên quan trong bài đang học (không gọi LLM)."""
from app.agents.base import AgentResult, Handoff, TurnContext
from app.ai.embeddings import EmbeddingClient
from app.retrieval import search_knowledge

TOP_K = 6
FIGURE_IN_TOP = 3  # có hình trong 3 kết quả đầu → nhờ Vision


class KnowledgeAgent:
    name = "knowledge"

    def __init__(self, embeddings: EmbeddingClient):
        self.embeddings = embeddings

    async def run(self, ctx: TurnContext):
        found = await search_knowledge(self.embeddings, ctx.text or "", ctx.lesson_id, TOP_K)
        pages = sorted({e.page for e in found})
        target = "vision" if any(e.kind == "figure" for e in found[:FIGURE_IN_TOP]) else "tutor"
        yield AgentResult(self.name, "", citations=tuple(e.chunk_id for e in found),
                          handoff=Handoff(target, f"tìm thấy {len(found)} đoạn, trang {', '.join(map(str, pages))}"
                                          if found else "không tìm thấy đoạn nào", {"evidence": found}))
