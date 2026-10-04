import pytest

from app.ingest import parse_args, run
from tests import pdfs
from tests.ingestion.conftest import GRAPH

pytestmark = pytest.mark.usefixtures("pool")


async def test_import_textbook(db, deps, tmp_path, capsys):
    pdf = tmp_path / "toan8.pdf"
    pdf.write_bytes(pdfs.lessons_pdf())
    deps.llm.script(GRAPH)
    code = await run(parse_args([str(pdf), "--title", "Toán 8 tập 2", "--subject", "toan", "--grade", "8"]), deps)
    assert code == 0
    kind, uploaded_by, status = db.execute("SELECT kind, uploaded_by, status FROM documents").fetchone()
    assert (kind, uploaded_by, status) == ("textbook", None, "ready")
    out = capsys.readouterr().out
    assert "lessons 2" in out and "figure chunks 1" in out and "text chunks" in out


async def test_invalid_file_creates_nothing(db, deps, tmp_path, capsys):
    bad = tmp_path / "anh.pdf"
    bad.write_bytes(pdfs.png())
    code = await run(parse_args([str(bad), "--title", "X", "--subject", "toan", "--grade", "8"]), deps)
    assert code == 1 and "not a PDF" in capsys.readouterr().err
    assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


def test_bad_subject_rejected():
    with pytest.raises(SystemExit):
        parse_args(["f.pdf", "--title", "X", "--subject", "math", "--grade", "8"])
