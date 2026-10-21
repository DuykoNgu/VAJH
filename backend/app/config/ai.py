"""LLM: provider, key, model cho từng route."""
from typing import Literal

from pydantic import BaseModel, model_validator

from app.config.core import CoreConfig


class Route(BaseModel):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]


# Mỗi agent gọi LLM qua một "route"; đổi model/effort chỉ cần đổi cấu hình
ROUTE_EFFORTS = {
    "orchestrator": "low",
    "knowledge": "low",
    "tutor": "low",  # đo trên máy demo: medium 19,6 s / low 3,1 s cho cùng một ý, lời giảng như nhau
    "assessment": "low",  # chấm câu trả lời: medium 3,3 s / low ~2 s, chấm vẫn đúng
    "vision_live": "medium",
    "vision_offline": "high",
    "document": "medium",
    "ocr_cleanup": "low",  # sửa chữ OCR local (chỉ gửi chữ): việc máy móc, không cần suy luận nhiều
    "toc": "low",  # đọc mục lục: effort medium mất nhiều phút với SGK thật, low ~20 s và vẫn đúng
    "outline": "low",  # dàn ý giảng (một lượt / bài): low ~6 s, đúng 5 ý của Bài 1 Toán 8
    "student_model": "medium",
}
ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"


def default_routes(provider: str, openai_model: str | None) -> dict[str, Route]:
    # OpenAI: chưa có model mặc định cho tới khi chọn (OPENAI_LLM_MODEL); "" → lỗi ở lần gọi đầu tiên
    model = (openai_model or "") if provider == "openai" else ANTHROPIC_DEFAULT_MODEL
    return {name: Route(model=model, effort=effort) for name, effort in ROUTE_EFFORTS.items()}


class AIConfig(CoreConfig):
    llm_provider: Literal["openai", "anthropic", "fake"] | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_llm_model: str | None = None
    # Chỉ ghi các route muốn đổi; phần còn lại giữ mặc định
    llm_routes: dict[str, Route] = {}
    llm_timeout_s: float = 180  # mỗi lần gọi LLM (SDK mặc định 600 s × 3 lần thử: một kết nối treo giữ cả việc nạp sách)

    @model_validator(mode="after")
    def _ai_defaults(self):
        test = self.app_env == "test"
        self.llm_provider = self.llm_provider or ("fake" if test else "openai")
        self.llm_routes = {**default_routes(self.llm_provider, self.openai_llm_model), **self.llm_routes}
        return self
