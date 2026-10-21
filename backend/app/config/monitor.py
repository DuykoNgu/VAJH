"""Trace agent + LLM cho trang /monitor."""
from typing import Literal

from pydantic import BaseModel, Field


class MonitorConfig(BaseModel):
    trace_payloads: Literal["all", "sampled"] = "sampled"  # sampled: lỗi/từ chối luôn đủ prompt, còn lại lấy mẫu
    trace_sample_rate: float = Field(0.25, ge=0, le=1)
    trace_payload_days: int = 7    # sau đó bỏ prompt/câu trả lời của trace chưa được đánh giá
    trace_keep_days: int = 90      # sau đó xoá hẳn trace
    llm_price_in_per_m: float | None = None   # USD / 1 triệu token vào, để /monitor ước tính chi phí (tuỳ chọn)
    llm_price_out_per_m: float | None = None  # USD / 1 triệu token ra
