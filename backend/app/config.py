"""Cấu hình LUSIA: đọc từ biến môi trường (và backend/.env), kiểm tra ngay khi khởi động."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


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


def default_routes(provider: str, openai_model: str | None) -> dict[str, "Route"]:
    # OpenAI: chưa có model mặc định cho tới khi chọn (OPENAI_LLM_MODEL); "" → lỗi ở lần gọi đầu tiên
    model = (openai_model or "") if provider == "openai" else ANTHROPIC_DEFAULT_MODEL
    return {name: Route(model=model, effort=effort) for name, effort in ROUTE_EFFORTS.items()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    # Chỉ có chế độ dev cho tới giai đoạn 12 (authentication)
    auth_mode: Literal["dev"] = "dev"
    dev_student_username: str = "minh8a"
    dev_teacher_username: str = "colan"

    database_url: str
    database_url_unpooled: str | None = None
    redis_url: str

    s3_endpoint_url: str | None = None
    s3_bucket: str = "lusia"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    frontend_origins: str = "http://localhost:3000"

    # Nạp tài liệu (document-ingestion). File lưu trên đĩa cho tới khi có S3 (foundations task 3.3)
    file_store: Literal["local"] = "local"
    files_dir: Path = BACKEND_DIR / "data" / "files"
    max_upload_mb: int = 50
    max_pages: int = 400
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 200
    figure_min_area_ratio: float = 0.02
    llm_concurrency: int = 4
    ingest_timeout_s: int = 3600
    trace_payloads: Literal["all", "sampled"] = "sampled"  # sampled: lỗi/từ chối luôn đủ prompt, còn lại lấy mẫu
    trace_sample_rate: float = Field(0.25, ge=0, le=1)
    trace_payload_days: int = 7    # sau đó bỏ prompt/câu trả lời của trace chưa được đánh giá
    trace_keep_days: int = 90      # sau đó xoá hẳn trace
    llm_price_in_per_m: float | None = None   # USD / 1 triệu token vào, để /monitor ước tính chi phí (tuỳ chọn)
    llm_price_out_per_m: float | None = None  # USD / 1 triệu token ra
    llm_timeout_s: float = 180  # mỗi lần gọi LLM (SDK mặc định 600 s × 3 lần thử: một kết nối treo giữ cả việc nạp sách)

    llm_provider: Literal["openai", "anthropic", "fake"] | None = None
    embedding_provider: Literal["local", "fake"] | None = None
    stt_provider: Literal["fake"] = "fake"
    tts_provider: Literal["zerotts", "fake"] | None = None
    zerotts_model_dir: Path = BACKEND_DIR / "data" / "models" / "zerotts"
    prefetch_parts: bool = True  # soạn sẵn ý kế tiếp trong lúc học sinh trả lời câu hỏi kiểm tra
    outline_on_ingest: bool = True  # nạp sách xong thì rút dàn ý giảng cho từng bài (một lượt LLM / bài)
    local_ocr: bool = True  # trang scan: OCR của macOS + LLM chỉ sửa chữ (rẻ hơn ~7 lần token vào); False → OCR bằng LLM
    layout_model_path: Path = BACKEND_DIR / "data" / "models" / "doclayout" / "doclayout_yolo_docstructbench_imgsz1024.pt"
    zerotts_voice: str = "baotrang"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_llm_model: str | None = None
    embedding_model: str = "AITeamVN/Vietnamese_Embedding_v2"
    # Chỉ ghi các route muốn đổi; phần còn lại giữ mặc định
    llm_routes: dict[str, Route] = {}

    @model_validator(mode="after")
    def _defaults_and_production_keys(self):
        if not self.zerotts_model_dir.is_absolute():
            self.zerotts_model_dir = BACKEND_DIR / self.zerotts_model_dir
        if not self.layout_model_path.is_absolute():
            self.layout_model_path = BACKEND_DIR / self.layout_model_path
        if not self.files_dir.is_absolute():  # đường dẫn tương đối tính từ backend/, không phụ thuộc thư mục đang chạy
            self.files_dir = BACKEND_DIR / self.files_dir
        test = self.app_env == "test"
        self.llm_provider = self.llm_provider or ("fake" if test else "openai")
        self.llm_routes = {**default_routes(self.llm_provider, self.openai_llm_model), **self.llm_routes}
        self.embedding_provider = self.embedding_provider or ("fake" if test else "local")
        self.tts_provider = self.tts_provider or ("fake" if test else "zerotts")
        if self.app_env == "production":
            missing = [
                name
                for name, needed, value in [
                    ("ANTHROPIC_API_KEY", self.llm_provider == "anthropic", self.anthropic_api_key),
                    ("OPENAI_API_KEY", self.llm_provider == "openai", self.openai_api_key),
                    ("OPENAI_LLM_MODEL", self.llm_provider == "openai"
                     and any(not r.model for r in self.llm_routes.values()), self.openai_llm_model),
                ]
                if needed and not value
            ]
            problems = [f"{name} is required in production" for name in missing]
            if self.auth_mode == "dev":
                # Danh tính dev (không xác thực) không bao giờ được chạy thật
                problems.append("AUTH_MODE=dev is not allowed with APP_ENV=production")
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


class ConfigError(SystemExit):
    pass


def load_settings(**kwargs) -> Settings:
    """Đọc cấu hình; lỗi thì dừng tiến trình và nêu tên TỪNG biến bị thiếu/sai."""
    try:
        return Settings(**kwargs)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            name = "_".join(str(p) for p in err["loc"]).upper()
            problems.append(f"{name}: {err['msg']}" if name else err["msg"].removeprefix("Value error, "))
        raise ConfigError("Invalid configuration: " + "; ".join(problems)) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
