"""Học sinh học bài."""
from pydantic import BaseModel


class LearningConfig(BaseModel):
    prefetch_parts: bool = True  # soạn sẵn ý kế tiếp trong lúc học sinh trả lời câu hỏi kiểm tra
