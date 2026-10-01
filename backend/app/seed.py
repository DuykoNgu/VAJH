"""Tạo dữ liệu demo (idempotent) cho chế độ danh tính dev:  python -m app.seed

Người dùng seed KHÔNG có mật khẩu/PIN dùng được (NO_CREDENTIAL); giai đoạn 12 mới cấp.
"""
import sys

import psycopg

from app.config import get_settings
from app.identity import DEV_USER_HEADER, NO_CREDENTIAL

TEACHER = ("colan", "Cô Lan")
CLASS_NAME = "8A"
STUDENTS = [("minh8a", "Em Minh", 8, "vi"), ("hana8a", "Hana", 8, "ja")]


def _user(conn, username: str, full_name: str):
    conn.execute("INSERT INTO users (full_name, username, password_hash) VALUES (%s, %s, %s)"
                 " ON CONFLICT (username) DO NOTHING", (full_name, username, NO_CREDENTIAL))
    return conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()[0]


def seed(url: str) -> None:
    with psycopg.connect(url, prepare_threshold=None) as conn, conn.transaction():
        teacher_id = _user(conn, *TEACHER)
        conn.execute("INSERT INTO teachers (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (teacher_id,))
        row = conn.execute("SELECT id FROM classes WHERE teacher_id = %s AND name = %s",
                           (teacher_id, CLASS_NAME)).fetchone()
        class_id = row[0] if row else conn.execute(
            "INSERT INTO classes (teacher_id, name) VALUES (%s, %s) RETURNING id", (teacher_id, CLASS_NAME)).fetchone()[0]
        for username, full_name, grade, language in STUDENTS:
            sid = _user(conn, username, full_name)
            conn.execute("INSERT INTO students (user_id, grade, language) VALUES (%s, %s, %s)"
                         " ON CONFLICT DO NOTHING", (sid, grade, language))
            conn.execute("INSERT INTO class_students (class_id, student_id) VALUES (%s, %s)"
                         " ON CONFLICT DO NOTHING", (class_id, sid))


def main() -> int:
    seed(get_settings().database_url)
    print(f"teacher  {TEACHER[0]:8} ({TEACHER[1]}), class {CLASS_NAME}")
    for username, full_name, grade, language in STUDENTS:
        print(f"student  {username:8} ({full_name}), grade {grade}, language {language}")
    print(f"No passwords/PINs (development identity). Choose a user with the header "
          f"`{DEV_USER_HEADER}: <username>`; without it the API acts as the configured default student/teacher.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
