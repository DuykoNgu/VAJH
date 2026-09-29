"""Học sinh ↔ LUSIA: nhận giọng nói / ảnh / PDF → Orchestrator → phản hồi bằng giọng nói."""
from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])
