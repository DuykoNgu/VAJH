"""GET /me: người dùng hiện tại. Cùng hình dạng response ở chế độ dev và khi có đăng nhập (phase 12)."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.identity import CurrentUser, UserContext

router = APIRouter(tags=["identity"])


class Me(BaseModel):
    mode: str
    user_id: UUID
    full_name: str
    username: str
    role: Literal["student", "teacher"]
    grade: int | None
    language: Literal["vi", "ja"] | None
    speech_rate: float | None


@router.get("/me", response_model=Me)
async def me(request: Request, user: UserContext = CurrentUser) -> Me:
    return Me(mode=request.app.state.identity_provider.mode, user_id=user.user_id, full_name=user.full_name,
              username=user.username, role=user.role, grade=user.grade, language=user.language,
              speech_rate=user.speech_rate)
