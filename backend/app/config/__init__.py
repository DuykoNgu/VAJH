"""Cấu hình LUSIA: đọc từ biến môi trường (và backend/.env), kiểm tra ngay khi khởi động.

Mỗi feature khai báo phần cấu hình của mình trong một file cạnh đây; Settings ghép lại thành một đối tượng phẳng
(tên biến môi trường = tên field, ví dụ MAX_PAGES → settings.max_pages).
"""
from functools import lru_cache

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.ai import AIConfig
from app.config.core import CoreConfig
from app.config.documents import DocumentsConfig
from app.config.learning import LearningConfig
from app.config.monitor import MonitorConfig
from app.config.paths import BACKEND_DIR
from app.config.rag import RAGConfig
from app.config.voice import VoiceConfig


class Settings(AIConfig, RAGConfig, VoiceConfig, DocumentsConfig, LearningConfig, MonitorConfig, CoreConfig,
               BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    @model_validator(mode="after")
    def _production_keys(self):
        # Chạy sau validator của từng phần (provider và route đã có giá trị mặc định)
        if self.app_env != "production":
            return self
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
