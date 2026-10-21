"""RAG / Knowledge Agent: tìm đoạn SGK liên quan trong bài đang học (không gọi LLM)."""
from app.core.rag.embeddings import EmbeddingClient
from app.core.rag.retrieval import search_knowledge
from app.features.learning.agents.base import AgentResult, Handoff, TurnContext

FIGURE_IN_TOP = 3  # có hình trong 3 kết quả đầu → nhờ Vision


class KnowledgeAgent:
    name = "knowledge"

    def __init__(self, embeddings: EmbeddingClient, top_k: int):
        self.embeddings = embeddings
        self.top_k = top_k

    async def run(self, ctx: TurnContext):
        found = await search_knowledge(self.embeddings, ctx.text or "", ctx.lesson_id, self.top_k)
        pages = sorted({e.page for e in found})
        target = "vision" if any(e.kind == "figure" for e in found[:FIGURE_IN_TOP]) else "tutor"
        yield AgentResult(self.name, "", citations=tuple(e.chunk_id for e in found),
                          handoff=Handoff(target, f"tìm thấy {len(found)} đoạn, trang {', '.join(map(str, pages))}"
                                          if found else "không tìm thấy đoạn nào", {"evidence": found}))
