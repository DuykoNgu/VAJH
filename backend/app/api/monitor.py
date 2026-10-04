"""Giám sát agent + LLM: số liệu tổng hợp, danh sách trace, chi tiết từng trace, chấm điểm trace (trang /monitor)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.agents.tutor import NOT_FOUND
from app.identity import CurrentTeacher, UserContext
from app.storage import relational

router = APIRouter(prefix="/monitor", tags=["monitor"])
Kind = Literal["lesson_start", "turn", "preview", "ingest"]


class KindStats(BaseModel):
    kind: str
    count: int
    errors: int
    p50_ms: float
    p95_ms: float


class RouteStats(BaseModel):
    route: str
    calls: int
    errors: int
    refusals: int
    p50_ms: float
    p95_ms: float
    input_tokens: int
    output_tokens: int


class AgentStats(BaseModel):
    agent: str
    runs: int
    errors: int
    p50_ms: float
    p95_ms: float


class Quality(BaseModel):
    turns: int
    not_found_rate: float | None  # tỉ lệ câu trả lời "không tìm thấy trong SGK"
    check_answers: int
    average_score: float | None  # điểm trung bình câu hỏi kiểm tra / quiz (0-1)
    thumbs_up: int
    thumbs_down: int


class Summary(BaseModel):
    hours: int
    kinds: list[KindStats]
    routes: list[RouteStats]
    agents: list[AgentStats]
    quality: Quality
    estimated_cost_usd: float | None  # cần LLM_PRICE_IN_PER_M và LLM_PRICE_OUT_PER_M


class TraceRow(BaseModel):
    id: UUID
    kind: str
    started_at: datetime
    duration_ms: int
    status: str
    error: str | None
    input: str | None
    output: str | None
    llm_calls: int
    input_tokens: int
    output_tokens: int
    rating: int | None
    note: str | None


class SpanOut(BaseModel):
    seq: int
    parent_seq: int | None
    kind: str
    name: str
    offset_ms: int
    duration_ms: int
    status: str
    model: str | None
    effort: str | None
    input_tokens: int | None
    output_tokens: int | None
    detail: dict[str, Any]


class TraceDetail(TraceRow):
    session_id: UUID | None
    document_id: UUID | None
    spans: list[SpanOut]


class Rating(BaseModel):
    rating: Literal[-1, 1] | None
    note: str | None = Field(default=None, max_length=2000)


class RouteConfig(BaseModel):
    route: str
    model: str
    effort: str


async def _rows(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


WINDOW = "started_at > now() - make_interval(hours => %s)"
P50_P95 = ("coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY {0}), 0),"
           " coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY {0}), 0)")


@router.get("/summary", response_model=Summary)
async def summary(request: Request, hours: int = Query(24, ge=1, le=24 * 30),
                  teacher: UserContext = CurrentTeacher) -> Summary:
    # authz-later: chỉ quản trị viên / giáo viên phụ trách xem được giám sát
    kinds = await _rows(f"SELECT kind, count(*), count(*) FILTER (WHERE status = 'error'), "
                        f"{P50_P95.format('duration_ms')} FROM traces WHERE {WINDOW} GROUP BY kind ORDER BY kind",
                        (hours,))
    spans = (f"FROM trace_spans s JOIN traces t ON t.id = s.trace_id WHERE t.{WINDOW} AND s.kind = %s "
             "GROUP BY s.name ORDER BY s.name")
    routes = await _rows(
        "SELECT s.name, count(*), count(*) FILTER (WHERE s.status = 'error'), count(*) FILTER (WHERE s.status = "
        f"'refusal'), {P50_P95.format('s.duration_ms')}, coalesce(sum(s.input_tokens), 0), "
        f"coalesce(sum(s.output_tokens), 0) {spans}", (hours, "llm"))
    agents = await _rows(f"SELECT s.name, count(*), count(*) FILTER (WHERE s.status = 'error'), "
                         f"{P50_P95.format('s.duration_ms')} {spans}", (hours, "agent"))
    turns, not_found, up, down = (await _rows(
        f"SELECT count(*) FILTER (WHERE kind = 'turn'), count(*) FILTER (WHERE kind = 'turn' AND output LIKE %s),"
        f" count(*) FILTER (WHERE rating = 1), count(*) FILTER (WHERE rating = -1) FROM traces WHERE {WINDOW}",
        (f"%{NOT_FOUND}%", hours)))[0]
    answered, average = (await _rows("SELECT count(*), avg(score) FROM answers"
                                     " WHERE answered_at > now() - make_interval(hours => %s)", (hours,)))[0]
    settings = request.app.state.settings
    cost = None
    if settings.llm_price_in_per_m is not None and settings.llm_price_out_per_m is not None:
        cost = round(sum(r[6] for r in routes) * settings.llm_price_in_per_m / 1e6
                     + sum(r[7] for r in routes) * settings.llm_price_out_per_m / 1e6, 4)
    return Summary(
        hours=hours,
        kinds=[KindStats(kind=r[0], count=r[1], errors=r[2], p50_ms=r[3], p95_ms=r[4]) for r in kinds],
        routes=[RouteStats(route=r[0], calls=r[1], errors=r[2], refusals=r[3], p50_ms=r[4], p95_ms=r[5],
                           input_tokens=r[6], output_tokens=r[7]) for r in routes],
        agents=[AgentStats(agent=r[0], runs=r[1], errors=r[2], p50_ms=r[3], p95_ms=r[4]) for r in agents],
        quality=Quality(turns=turns, not_found_rate=not_found / turns if turns else None, check_answers=answered,
                        average_score=float(average) if average is not None else None, thumbs_up=up,
                        thumbs_down=down),
        estimated_cost_usd=cost)


TRACE_SQL = (
    "SELECT t.id, t.kind, t.started_at, t.duration_ms, t.status, t.error, left(t.input, 300), left(t.output, 300),"
    " count(s.seq) FILTER (WHERE s.kind = 'llm'), coalesce(sum(s.input_tokens), 0), coalesce(sum(s.output_tokens), 0),"
    " t.rating, t.note, t.session_id, t.document_id"
    " FROM traces t LEFT JOIN trace_spans s ON s.trace_id = t.id")


def _row(r) -> dict:
    return dict(id=r[0], kind=r[1], started_at=r[2], duration_ms=r[3], status=r[4], error=r[5], input=r[6],
                output=r[7], llm_calls=r[8], input_tokens=r[9], output_tokens=r[10], rating=r[11], note=r[12])


@router.get("/traces", response_model=list[TraceRow])
async def traces(kind: Kind | None = None, status: Literal["ok", "error"] | None = None,
                 rated: Literal["up", "down", "any"] | None = None,
                 order: Literal["recent", "slowest"] = "recent", limit: int = Query(50, ge=1, le=200),
                 teacher: UserContext = CurrentTeacher) -> list[TraceRow]:
    rating = {"up": "t.rating = 1", "down": "t.rating = -1", "any": "t.rating IS NOT NULL", None: "TRUE"}[rated]
    rows = await _rows(
        TRACE_SQL + f" WHERE (%s::text IS NULL OR t.kind = %s) AND (%s::text IS NULL OR t.status = %s) AND {rating}"
        f" GROUP BY t.id ORDER BY {'t.duration_ms DESC' if order == 'slowest' else 't.started_at DESC'} LIMIT %s",
        (kind, kind, status, status, limit))
    return [TraceRow(**_row(r)) for r in rows]


async def _detail(trace_id: UUID) -> TraceDetail:
    rows = await _rows(TRACE_SQL.replace("left(t.input, 300)", "t.input").replace("left(t.output, 300)", "t.output")
                       + " WHERE t.id = %s GROUP BY t.id", (trace_id,))
    if not rows:
        raise HTTPException(404, "trace not found")
    spans = await _rows("SELECT seq, parent_seq, kind, name, offset_ms, duration_ms, status, model, effort,"
                        " input_tokens, output_tokens, detail FROM trace_spans WHERE trace_id = %s ORDER BY seq",
                        (trace_id,))
    r = rows[0]
    return TraceDetail(**_row(r), session_id=r[13], document_id=r[14], spans=[SpanOut(
        seq=s[0], parent_seq=s[1], kind=s[2], name=s[3], offset_ms=s[4], duration_ms=s[5], status=s[6], model=s[7],
        effort=s[8], input_tokens=s[9], output_tokens=s[10], detail=s[11]) for s in spans])


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def trace_detail(trace_id: UUID, teacher: UserContext = CurrentTeacher) -> TraceDetail:
    return await _detail(trace_id)


@router.post("/traces/{trace_id}/rating", response_model=TraceDetail)
async def rate(trace_id: UUID, body: Rating, teacher: UserContext = CurrentTeacher) -> TraceDetail:
    async with relational.connection() as conn:
        found = await (await conn.execute(
            "UPDATE traces SET rating = %s, note = %s, rated_by = %s WHERE id = %s RETURNING id",
            (body.rating, body.note or None, teacher.teacher_id, trace_id))).fetchone()
    if found is None:
        raise HTTPException(404, "trace not found")
    return await _detail(trace_id)


@router.get("/routes", response_model=list[RouteConfig])
async def routes(request: Request, teacher: UserContext = CurrentTeacher) -> list[RouteConfig]:
    """Cấu hình route LLM đang chạy (đổi qua OPENAI_LLM_MODEL / LLM_ROUTES rồi khởi động lại API)."""
    return [RouteConfig(route=name, model=r.model, effort=r.effort)
            for name, r in sorted(request.app.state.settings.llm_routes.items())]
