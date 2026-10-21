"""Hạ tầng dùng chung: môi trường, danh tính dev, database, Redis, lưu file, CORS."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

from app.config.paths import BACKEND_DIR, absolute


class CoreConfig(BaseModel):
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

    # File lưu trên đĩa cho tới khi có S3 (foundations task 3.3)
    file_store: Literal["local"] = "local"
    files_dir: Path = BACKEND_DIR / "data" / "files"

    frontend_origins: str = "http://localhost:3000"

    _files_dir = field_validator("files_dir")(absolute)

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]
