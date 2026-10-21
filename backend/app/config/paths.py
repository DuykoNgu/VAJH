from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def absolute(path: Path) -> Path:
    """Đường dẫn tương đối tính từ backend/, không phụ thuộc thư mục đang chạy."""
    return path if path.is_absolute() else BACKEND_DIR / path
