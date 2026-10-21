"""Teacher Dashboard: lớp nào, học sinh nào yếu ở bài nào (hiểu bài hay hiểu hình), và duyệt mô tả hình của AI."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.identity import CurrentTeacher, UserContext
from app.core.rag.indexing import reindex_chunk
from app.core.storage import relational

router = APIRouter(prefix="/teacher", tags=["teacher"])
WEAK_BELOW = 0.5


class LessonMastery(BaseModel):
    lesson_id: UUID
    title: str
    answered: int
    mastery: float
    concept_mastery: float | None
    figure_mastery: float | None
    last_practiced_at: datetime
    weak: bool
    weak_in: list[Literal["concept", "figure"]]


class StudentOverview(BaseModel):
    student_id: UUID
    full_name: str
    username: str
    lessons: list[LessonMastery]


class ClassOverview(BaseModel):
    class_id: UUID
    name: str
    students: list[StudentOverview]


class Figure(BaseModel):
    id: int
    document_title: str
    lesson_title: str | None
    page: int
    description: str
    review: Literal["pending", "approved", "rejected"]
    image_url: str


class Review(BaseModel):
    action: Literal["approve", "reject"]
    description: str | None = Field(default=None, min_length=1)


async def _rows(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


def _f(value) -> float | None:
    return None if value is None else float(value)


@router.get("/overview", response_model=list[ClassOverview])
async def overview(teacher: UserContext = CurrentTeacher) -> list[ClassOverview]:
    rows = await _rows(
        "SELECT c.id, c.name, u.id, u.full_name, u.username, l.id, l.title, m.answered, m.mastery,"
        " m.concept_mastery, m.figure_mastery, m.last_practiced_at"
        " FROM classes c"
        " LEFT JOIN class_students cs ON cs.class_id = c.id"
        " LEFT JOIN users u ON u.id = cs.student_id"
        " LEFT JOIN lesson_mastery m ON m.student_id = u.id"
        " LEFT JOIN lessons l ON l.id = m.lesson_id"
        " WHERE c.teacher_id = %s ORDER BY c.name, u.full_name, l.title", (teacher.teacher_id,))
    classes: dict[UUID, ClassOverview] = {}
    students: dict[tuple, StudentOverview] = {}
    for cid, cname, sid, full, uname, lid, title, answered, mastery, concept, figure, last in rows:
        cls = classes.setdefault(cid, ClassOverview(class_id=cid, name=cname, students=[]))
        if sid is None:
            continue
        if (cid, sid) not in students:
            students[(cid, sid)] = StudentOverview(student_id=sid, full_name=full, username=uname, lessons=[])
            cls.students.append(students[(cid, sid)])
        if lid is None:
            continue
        parts = {"concept": _f(concept), "figure": _f(figure)}
        weak_in = [p for p, v in parts.items() if v is not None and v < WEAK_BELOW]
        students[(cid, sid)].lessons.append(LessonMastery(
            lesson_id=lid, title=title, answered=answered, mastery=float(mastery), concept_mastery=parts["concept"],
            figure_mastery=parts["figure"], last_practiced_at=last,
            weak=float(mastery) < WEAK_BELOW or bool(weak_in), weak_in=weak_in))
    return list(classes.values())


FIGURE_SQL = (
    "SELECT c.id, d.title, l.title, c.page, c.content, c.review FROM chunks c"
    " JOIN documents d ON d.id = c.document_id LEFT JOIN lessons l ON l.id = c.lesson_id"
    " WHERE c.kind = 'figure'")


def _figure(r) -> Figure:
    return Figure(id=r[0], document_title=r[1], lesson_title=r[2], page=r[3], description=r[4], review=r[5],
                  image_url=f"/figures/{r[0]}/image")


@router.get("/figures", response_model=list[Figure])
async def figures(status: Literal["pending", "approved", "rejected"] = "pending",
                  teacher: UserContext = CurrentTeacher) -> list[Figure]:
    # authz-later: chỉ hình trong tài liệu của lớp mình / SGK được phép duyệt
    return [_figure(r) for r in await _rows(FIGURE_SQL + " AND c.review = %s ORDER BY d.title, c.page, c.id",
                                            (status,))]


@router.post("/figures/{chunk_id}/review", response_model=Figure)
async def review_figure(request: Request, chunk_id: int, body: Review,
                        teacher: UserContext = CurrentTeacher) -> Figure:
    # authz-later: chỉ hình trong tài liệu của lớp mình / SGK được phép duyệt
    found = await _rows(FIGURE_SQL + " AND c.id = %s", (chunk_id,))
    if not found:
        raise HTTPException(404, "figure not found")
    async with relational.transaction() as conn:
        if body.action == "approve" and body.description and body.description.strip() != found[0][4]:
            text = body.description.strip()
            await reindex_chunk(conn, request.app.state.embeddings, chunk_id, text)
        await conn.execute("UPDATE chunks SET review = %s, reviewed_by = %s, reviewed_at = now() WHERE id = %s",
                           ("approved" if body.action == "approve" else "rejected", teacher.teacher_id, chunk_id))
    return _figure((await _rows(FIGURE_SQL + " AND c.id = %s", (chunk_id,)))[0])
