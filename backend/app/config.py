"""Cấu hình LUSIA: đọc từ biến môi trường (và backend/.env), kiểm tra ngay khi khởi động."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Route(BaseModel):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]


# Mỗi agent gọi LLM qua một "route"; đổi model/effort chỉ cần đổi cấu hình
ROUTE_EFFORTS = {
    "orchestrator": "low",
    "knowledge": "low",
    "tutor": "medium",
    "assessment": "medium",
    "vision_live": "medium",
    "vision_offline": "high",
    "document": "medium",
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

    llm_provider: Literal["openai", "anthropic", "fake"] | None = None
    embedding_provider: Literal["openai", "fake"] | None = None
    stt_provider: Literal["fake"] = "fake"
    tts_provider: Literal["fake"] = "fake"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_llm_model: str | None = None
    embedding_model: str = "text-embedding-3-small"
    # Chỉ ghi các route muốn đổi; phần còn lại giữ mặc định
    llm_routes: dict[str, Route] = {}

    @model_validator(mode="after")
    def _defaults_and_production_keys(self):
        test = self.app_env == "test"
        self.llm_provider = self.llm_provider or ("fake" if test else "openai")
        self.llm_routes = {**default_routes(self.llm_provider, self.openai_llm_model), **self.llm_routes}
        self.embedding_provider = self.embedding_provider or ("fake" if test else "openai")
        if self.app_env == "production":
            missing = [
                name
                for name, needed, value in [
                    ("ANTHROPIC_API_KEY", self.llm_provider == "anthropic", self.anthropic_api_key),
                    ("OPENAI_API_KEY", "openai" in (self.llm_provider, self.embedding_provider), self.openai_api_key),
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
