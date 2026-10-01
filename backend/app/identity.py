"""Danh tính người dùng - ĐIỂM THAY THẾ DUY NHẤT khi có đăng nhập (giai đoạn 12, change `authentication`).

Endpoint chỉ lấy người dùng qua current_student / current_teacher / current_user và truyền id tường minh
xuống service. Không module nào khác được đọc header dev hay cấu hình DEV_* (tests/test_identity_isolation.py).

Hiện chỉ có AUTH_MODE=dev: header `X-Dev-User: <username>` chọn người dùng; không có header thì dùng
DEV_STUDENT_USERNAME / DEV_TEACHER_USERNAME tùy endpoint cần học sinh hay giáo viên. KHÔNG xác thực gì cả.
"""
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection

from app.config import Settings
from app.storage import relational

DEV_USER_HEADER = "X-Dev-User"
NO_CREDENTIAL = "!no-credential"  # không phải hash hợp lệ → không mật khẩu/PIN nào khớp được
Role = Literal["student", "teacher"]


@dataclass(frozen=True)
class UserContext:
    user_id: UUID
    full_name: str
    username: str
    role: Role
    grade: int | None = None
    language: Literal["vi", "ja"] | None = None
    speech_rate: float | None = None

    @property
    def student_id(self) -> UUID | None:
        return self.user_id if self.role == "student" else None

    @property
    def teacher_id(self) -> UUID | None:
        return self.user_id if self.role == "teacher" else None


class IdentityProvider(Protocol):
    mode: str

    async def resolve(self, conn: HTTPConnection, role: Role | None) -> UserContext:
        """role=None: người dùng hiện tại bất kể vai trò (dùng cho GET /me)."""


_LOOKUP = """
SELECT u.id, u.full_name, u.username, s.user_id IS NOT NULL, t.user_id IS NOT NULL,
       s.grade, s.language, s.speech_rate
FROM users u
LEFT JOIN students s ON s.user_id = u.id
LEFT JOIN teachers t ON t.user_id = u.id
WHERE u.username = %s
"""


async def lookup_user(username: str, role: Role | None) -> UserContext | None:
    async with relational.connection() as conn:
        row = await (await conn.execute(_LOOKUP, (username,))).fetchone()
    if row is None:
        return None
    uid, full_name, uname, is_student, is_teacher, grade, language, rate = row
    if role is None:
        role = "student" if is_student else "teacher" if is_teacher else None
    if role == "student" and is_student:
        return UserContext(uid, full_name, uname, "student", grade, language, float(rate))
    if role == "teacher" and is_teacher:
        return UserContext(uid, full_name, uname, "teacher")
    raise HTTPException(400, f"development user {uname!r} is not a {role or 'student or teacher'}")


class DevIdentityProvider:
    mode = "dev"

    def __init__(self, settings: Settings):
        self.defaults = {"student": settings.dev_student_username, "teacher": settings.dev_teacher_username}

    async def resolve(self, conn: HTTPConnection, role: Role | None) -> UserContext:
        header = conn.headers.get(DEV_USER_HEADER)
        if header and header.strip():
            username = header.strip().lower()
            user = await lookup_user(username, role)
            if user is None:
                raise HTTPException(400, f"development user {username!r} does not exist")
            return user
        username = self.defaults[role or "student"]
        user = await lookup_user(username, role or "student")
        if user is None:
            raise HTTPException(503, f"default development user {username!r} is missing - run `python -m app.seed`")
        return user


def make_identity_provider(settings: Settings) -> IdentityProvider:
    return DevIdentityProvider(settings)  # phase 12: AUTH_MODE=auth → AuthIdentityProvider


def _provider(conn: HTTPConnection) -> IdentityProvider:
    return conn.app.state.identity_provider


async def current_user(conn: HTTPConnection) -> UserContext:
    return await _provider(conn).resolve(conn, None)


async def current_student(conn: HTTPConnection) -> UserContext:
    return await _provider(conn).resolve(conn, "student")


async def current_teacher(conn: HTTPConnection) -> UserContext:
    return await _provider(conn).resolve(conn, "teacher")


CurrentUser = Depends(current_user)
CurrentStudent = Depends(current_student)
CurrentTeacher = Depends(current_teacher)
