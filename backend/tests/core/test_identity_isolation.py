"""Chỉ app/core/identity.py (và app/config/core.py) được biết tới danh tính dev → phase 12 chỉ cần thay provider."""
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
ALLOWED = {APP / "core" / "identity.py", APP / "config" / "core.py"}
FORBIDDEN = ["x-dev-user", "dev_student_username", "dev_teacher_username"]


def offenders(root=APP):
    found = []
    for path in root.rglob("*.py"):
        if path in ALLOWED:
            continue
        text = path.read_text().lower()
        found += [f"{path.relative_to(root.parent)}: {word}" for word in FORBIDDEN if word in text]
    return found


def test_only_identity_module_knows_the_dev_identity():
    assert offenders() == []


def test_scan_catches_a_leak(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "leaky.py").write_text('user = request.headers["X-Dev-User"]\n')
    assert offenders(tmp_path / "app") == ["app/leaky.py: x-dev-user"]
