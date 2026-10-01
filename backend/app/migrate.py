"""Áp dụng migration SQL theo thứ tự tên file, ghi lại file đã chạy.

    python -m app.migrate                       # áp các file chưa chạy
    python -m app.migrate --baseline 000_init   # đánh dấu đã chạy mà không thực thi (DB cũ tạo từ schema.sql)

Luôn dùng URL không qua pooler (DATABASE_URL_UNPOOLED), vì advisory lock và DDL cần một kết nối thật.
"""
import argparse
import sys
from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
LOCK_ID = 7_310_001  # số bất kỳ, cố định: chỉ một tiến trình migrate chạy cùng lúc


class MigrationError(Exception):
    pass


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"))


def migrate(url: str, directory: Path = MIGRATIONS_DIR, baseline: list[str] = ()) -> list[str]:
    """Trả về tên các file vừa áp dụng (hoặc vừa baseline)."""
    files = {f.stem: f for f in migration_files(directory)}
    unknown = [name for name in baseline if name not in files]
    if unknown:
        raise MigrationError(f"unknown migration(s) for baseline: {', '.join(unknown)}")

    applied_now = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
            # Chế độ baseline chỉ đánh dấu các file được nêu, không chạy file nào khác
            todo = [n for n in files if n not in done and (not baseline or n in baseline)]
            for name in todo:
                path = files[name]
                try:
                    with conn.transaction():
                        if not baseline:
                            conn.execute(path.read_text())
                        conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
                except psycopg.Error as e:
                    raise MigrationError(f"migration {path.name} failed: {e}") from e
                applied_now.append(name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return applied_now


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.migrate")
    parser.add_argument("--baseline", nargs="*", default=[], metavar="NAME",
                        help="mark these migrations as applied without running them (e.g. 000_init)")
    args = parser.parse_args(argv)
    settings = get_settings()
    url = settings.database_url_unpooled or settings.database_url
    try:
        applied = migrate(url, baseline=args.baseline)
    except MigrationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for name in applied:
        print(f"{'baselined' if name in args.baseline else 'applied'} {name}")
    if not applied:
        print("database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
