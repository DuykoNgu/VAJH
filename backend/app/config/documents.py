"""Nạp tài liệu (document-ingestion): giới hạn upload, tìm hình, OCR, dàn ý."""
from pathlib import Path

from pydantic import BaseModel, field_validator

from app.config.paths import BACKEND_DIR, absolute


class DocumentsConfig(BaseModel):
    max_upload_mb: int = 50
    max_pages: int = 400
    figure_min_area_ratio: float = 0.02
    llm_concurrency: int = 4
    ingest_timeout_s: int = 3600
    outline_on_ingest: bool = True  # nạp sách xong thì rút dàn ý giảng cho từng bài (một lượt LLM / bài)
    local_ocr: bool = True  # trang scan: OCR của macOS + LLM chỉ sửa chữ (rẻ hơn ~7 lần token vào); False → OCR bằng LLM
    layout_model_path: Path = BACKEND_DIR / "data" / "models" / "doclayout" / "doclayout_yolo_docstructbench_imgsz1024.pt"

    _layout_model_path = field_validator("layout_model_path")(absolute)
