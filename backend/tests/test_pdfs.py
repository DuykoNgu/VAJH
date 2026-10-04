import pymupdf
import pytest

from tests import pdfs


@pytest.mark.parametrize("make, pages", [(pdfs.lessons_pdf, 7), (pdfs.toc_pdf, 6), (pdfs.plain_pdf, 3),
                                         (pdfs.figures_pdf, 3), (pdfs.special_pages_pdf, 4)])
def test_generated_pdfs_open(make, pages):
    with pymupdf.open(stream=make(), filetype="pdf") as doc:
        assert doc.page_count == pages


def test_vietnamese_text_survives():
    with pymupdf.open(stream=pdfs.lessons_pdf(), filetype="pdf") as doc:
        assert "Hàm số bậc nhất" in doc[1].get_text()
        assert doc.get_toc()[1][1:] == ["Bài 2. Đồ thị của hàm số bậc nhất", 5]


def test_encrypted_pdf_needs_password():
    with pymupdf.open(stream=pdfs.encrypted_pdf(), filetype="pdf") as doc:
        assert doc.needs_pass
