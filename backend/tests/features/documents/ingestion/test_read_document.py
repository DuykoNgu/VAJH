import asyncio

import pytest

from app.config import get_settings
from app.core.ai.fakes import FakeLLM
from app.core.ai.llm import Refusal
from app.features.documents.ingestion.pdf import open_pdf, page_texts
from app.features.documents.tools import ToolError, read_document
from tests import pdfs


async def read(llm, data):
    progress = []

    async def on_page(done):
        progress.append(done)

    with open_pdf(data, 400) as doc:
        texts, ocr = await read_document(doc, page_texts(doc), llm, limit=asyncio.Semaphore(4), on_page=on_page)
    return texts, ocr, progress


async def test_only_unusable_pages_are_ocred():
    llm = FakeLLM(get_settings()).script("Bài 1. Hàm số bậc nhất (OCR)", "Trang scan (OCR)")
    texts, ocr, progress = await read(llm, pdfs.special_pages_pdf())
    assert ocr == 2 and len(llm.calls) == 2
    assert all(c["route"] == "document" for c in llm.calls)
    assert [b["type"] for b in llm.calls[0]["messages"][0]["content"]] == ["image", "text"]
    assert "Hàm số bậc nhất" in texts[0] and texts[1].strip() == ""
    assert set(texts[2:]) == {"Bài 1. Hàm số bậc nhất (OCR)", "Trang scan (OCR)"}
    assert progress[0] == 2 and progress[-1] == 4


async def test_digital_document_needs_no_llm():
    llm = FakeLLM(get_settings())
    texts, ocr, _ = await read(llm, pdfs.lessons_pdf())
    assert ocr == 0 and llm.calls == [] and "Bài 2" in texts[4]


async def test_refused_ocr_is_an_error():
    llm = FakeLLM(get_settings()).script(Refusal("other"), Refusal("other"))
    with pytest.raises(ToolError, match="OCR refused"):
        await read(llm, pdfs.special_pages_pdf())
