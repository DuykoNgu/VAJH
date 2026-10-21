"""RAG: cắt đoạn, model embedding, số đoạn lấy về mỗi câu hỏi."""
from typing import Literal

from pydantic import model_validator

from app.config.core import CoreConfig


class RAGConfig(CoreConfig):
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 200
    embedding_provider: Literal["local", "fake"] | None = None
    embedding_model: str = "AITeamVN/Vietnamese_Embedding_v2"
    rag_top_k: int = 6  # số đoạn Knowledge Agent lấy về cho mỗi câu hỏi

    @model_validator(mode="after")
    def _rag_defaults(self):
        self.embedding_provider = self.embedding_provider or ("fake" if self.app_env == "test" else "local")
        return self
