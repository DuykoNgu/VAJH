"""Học sinh ↔ LUSIA: phiên học, mỗi lượt hỏi (chữ - giọng nói được trình duyệt chuyển thành chữ) → các agent → trả lời."""
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import learning, tracing
from app.identity import CurrentStudent, UserContext

router = APIRouter(tags=["learning"])


class StartSession(BaseModel):
    lesson_id: UUID | None = None


class Turn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class TraceStep(BaseModel):
    agent: str
    summary: str


class Citation(BaseModel):
    chunk_id: int
    page: int
    kind: str


class TurnReply(BaseModel):
    answer: str
    sentences: list[str]
    trace: list[TraceStep]
    citations: list[Citation]
    mode: str
    trace_id: UUID | None = None  # xem chi tiết agent / LLM của lượt này ở /monitor


class SessionStarted(TurnReply):
    id: UUID
    lesson_title: str | None


def _http(e: learning.SessionError) -> HTTPException:
    return HTTPException(e.status, str(e))


@router.post("/sessions", status_code=201, response_model=SessionStarted)
async def start_session(request: Request, body: StartSession, student: UserContext = CurrentStudent) -> SessionStarted:
    try:
        sid, title = await learning.start_session(student.student_id, body.lesson_id)  # chủ phiên = học sinh hiện tại
    except learning.SessionError as e:
        raise _http(e) from None
    async with tracing.trace("lesson_start", session_id=sid, input=title) as t:
        reply = await learning.begin_lesson(sid, student, body.lesson_id, title, request.app.state.agents)
        t.output = reply.answer
    return SessionStarted(id=sid, lesson_title=title, trace_id=t.id, **asdict(reply))


@router.post("/sessions/{session_id}/turns", response_model=TurnReply)
async def take_turn(request: Request, session_id: UUID, body: Turn,
                    student: UserContext = CurrentStudent) -> TurnReply:
    # authz-later: phiên phải thuộc về học sinh hiện tại
    try:
        async with tracing.trace("turn", session_id=session_id, input=body.text.strip()) as t:
            reply = await learning.take_turn(session_id, student, body.text.strip(), request.app.state.agents)
            t.output = reply.answer
    except learning.SessionError as e:
        raise _http(e) from None
    return TurnReply(trace_id=t.id, **asdict(reply))


@router.post("/sessions/{session_id}/end", status_code=204)
async def end_session(session_id: UUID, student: UserContext = CurrentStudent) -> Response:
    # authz-later: phiên phải thuộc về học sinh hiện tại
    try:
        await learning.end_session(session_id)
    except learning.SessionError as e:
        raise _http(e) from None
    return Response(status_code=204)
