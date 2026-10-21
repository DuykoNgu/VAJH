import re

import pytest

from app.features.documents.ingestion.pdf import (
    PdfError,
    bookmarks,
    open_pdf,
    page_texts,
    render_png,
)
from tests import pdfs


def texts(data):
    with open_pdf(data, 400) as doc:
        return page_texts(doc)


def test_digital_page_usable_blank_usable_tcvn3_and_scan_unusable():
    digital, blank, tcvn3, scan = texts(pdfs.special_pages_pdf())
    assert digital.usable and "Hàm số bậc nhất" in digital.text
    assert blank.usable and blank.text.strip() == ""
    assert not tcvn3.usable and tcvn3.reason == "legacy Vietnamese font encoding"
    assert not scan.usable and scan.reason == "no text layer"


def test_all_pages_of_a_normal_textbook_are_usable():
    assert all(p.usable for p in texts(pdfs.lessons_pdf()))


@pytest.mark.parametrize("data, message", [
    (pdfs.png(), "not a PDF"),
    (b"%PDF-1.7 garbage that is not a pdf", "unreadable"),
    (pdfs.encrypted_pdf(), "encrypted"),
    (pdfs.many_pages_pdf(5), "5 pages (limit 4)"),
])
def test_validation_failures(data, message):
    with pytest.raises(PdfError, match=re.escape(message)):
        open_pdf(data, max_pages=4)


def test_bookmarks_and_render():
    with open_pdf(pdfs.lessons_pdf(), 400) as doc:
        assert bookmarks(doc) == [(1, "Bài 1. Hàm số bậc nhất", 2), (1, "Bài 2. Đồ thị của hàm số bậc nhất", 5)]
        assert render_png(doc[0]).startswith(b"\x89PNG")
