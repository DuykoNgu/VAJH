"""Trang scan: nhận ra trang scan, OCR local + LLM chỉ sửa chữ, lọc khung hình từ model bố cục."""
import asyncio

import pymupdf
import pytest

from app.ai.fakes import FakeLLM
from app.ai.llm import Refusal
from app.config import BACKEND_DIR, get_settings
from app.ingestion import scan
from app.ingestion.pdf import open_pdf, page_texts
from app.tools import read_document
from tests import pdfs


def test_full_page_image_is_scanned_text_page_is_not():
    with open_pdf(pdfs.special_pages_pdf(), 400) as doc:
        assert [scan.is_scanned(p) for p in doc] == [False, False, False, True]
    with open_pdf(pdfs.figures_pdf(), 400) as doc:  # ảnh minh hoạ nhỏ trong trang chữ: không phải scan
        assert not any(scan.is_scanned(p) for p in doc)


async def test_local_ocr_then_text_only_cleanup():
    llm = FakeLLM(get_settings()).script("Bài 1. Đa thức x^2 (đã sửa)", "Trang scan x^2 (đã sửa)")
    seen = []

    def fake_local(page):
        seen.append(page.number + 1)
        return f"OCR trang {page.number + 1}: x2"

    with open_pdf(pdfs.special_pages_pdf(), 400) as doc:
        texts, ocr = await read_document(doc, page_texts(doc), llm, limit=asyncio.Semaphore(4), local_ocr=fake_local)
    assert ocr == 2 and sorted(seen) == [3, 4]                                   # chỉ trang không dùng được lớp chữ
    assert all(c["route"] == "ocr_cleanup" for c in llm.calls)
    assert all(isinstance(c["messages"][0]["content"], str) for c in llm.calls)   # chỉ gửi chữ, không gửi ảnh
    assert set(texts[2:]) == {"Bài 1. Đa thức x^2 (đã sửa)", "Trang scan x^2 (đã sửa)"}


async def test_no_local_ocr_falls_back_to_llm_image_and_refusal_keeps_raw():
    llm = FakeLLM(get_settings()).script("OCR bằng ảnh", Refusal("other"))
    calls = iter([None, "chữ OCR thô"])  # trang 3: máy không OCR được → LLM đọc ảnh; trang 4: LLM từ chối sửa

    with open_pdf(pdfs.special_pages_pdf(), 400) as doc:
        texts, _ = await read_document(doc, page_texts(doc), llm, limit=asyncio.Semaphore(1),
                                       local_ocr=lambda page: next(calls))
    assert texts[2:] == ["OCR bằng ảnh", "chữ OCR thô"]
    assert [c["route"] for c in llm.calls] == ["document", "ocr_cleanup"]


def test_keep_boxes_filters_and_converts():
    page = pymupdf.Rect(0, 0, 720, 1000)
    boxes = [("figure", 0.94, (100, 100, 400, 300)),     # hình thật: giữ
             ("figure", 0.26, (10, 10, 500, 500)),       # không đủ tin cậy
             ("figure", 0.9, (10, 900, 60, 950)),        # biểu tượng nhỏ
             ("table", 0.85, (50, 10, 650, 130)),         # bảng: giữ (LLM quyết định có phải chỉ là chữ)
             ("isolate_formula", 0.9, (0, 400, 700, 500))]
    kept = scan.keep_boxes(boxes, 0.5, page, 0.02)
    assert kept == [pymupdf.Rect(25, 5, 325, 65), pymupdf.Rect(50, 50, 200, 150)]


def test_missing_layout_model_skips_figures(tmp_path):
    with open_pdf(pdfs.special_pages_pdf(), 400) as doc:
        assert scan.detect_figures(doc[3], tmp_path / "none.pt", 0.02) == []


MODEL = BACKEND_DIR / "data" / "models" / "doclayout" / "doclayout_yolo_docstructbench_imgsz1024.pt"


@pytest.mark.skipif(not MODEL.is_file(), reason="layout model not downloaded")
def test_real_layout_model_runs_on_a_scanned_page():
    with open_pdf(pdfs.special_pages_pdf(), 400) as doc:
        figures = scan.detect_figures(doc[3], MODEL, 0.02)   # trang ảnh trơn: chạy được, không có hình
    assert figures == []
