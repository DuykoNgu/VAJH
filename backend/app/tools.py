"""Tool Layer — các tool Orchestrator gọi cho agent:

search_knowledge, get_student_profile, save_learning_result, generate_quiz,
grade_answer, describe_image, read_document, create_learning_plan, send_teacher_report

Đã có: read_document (đọc PDF, OCR trang không có lớp chữ), describe_figure (dữ kiện của hình để giáo viên duyệt).
"""
import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Literal

import pymupdf
from pydantic import BaseModel

from app.ai.llm import LLMClient, Refusal, image_block
from app.ingestion.pdf import PageText, render_png

log = logging.getLogger("lusia.ingestion")

OCR_PROMPT = (
    "Chép lại CHÍNH XÁC toàn bộ chữ trên trang sách giáo khoa này, theo thứ tự đọc, giữ nguyên tiếng Việt có dấu "
    "và xuống dòng giữa các đoạn. Công thức viết dạng văn bản thường (ví dụ: y = 2x + 1). Không mô tả hình, không "
    "thêm lời giải thích. Nếu trang không có chữ, trả về chuỗi rỗng."
)


OCR_FIX_SYSTEM = (
    "Đây là chữ do OCR đọc từ một trang sách giáo khoa tiếng Việt. OCR thường làm mất số mũ, căn, phân số, chỉ số và "
    "sai dấu tiếng Việt. Sửa lại cho đúng theo ngữ cảnh: số mũ viết x^2, căn viết sqrt(2), phân số a/b; sửa chính tả. "
    "Bỏ chữ chìm (watermark) và số trang lẻ loi. Không dùng LaTeX hay ký hiệu như \\frac, \\( \\). KHÔNG thêm, bớt "
    "hay diễn giải nội dung. Chỉ trả lại văn bản đã sửa."
)


class ToolError(Exception):
    pass


async def ocr_page(llm: LLMClient, page: pymupdf.Page, route: str = "document") -> str:
    image = await asyncio.to_thread(render_png, page)
    result = await llm.complete(route, [{"role": "user", "content": [image_block(image, "image/png"),
                                                                       {"type": "text", "text": OCR_PROMPT}]}])
    if isinstance(result, Refusal):
        raise ToolError(f"page {page.number + 1}: OCR refused ({result.category or result.explanation})")
    return result.text.strip()


async def fix_ocr_text(llm: LLMClient, raw: str, route: str = "ocr_cleanup") -> str:
    """Sửa chữ OCR local bằng LLM (chỉ gửi chữ, không gửi ảnh); LLM từ chối → giữ chữ OCR."""
    if not raw.strip():
        return ""
    result = await llm.complete(route, [{"role": "user", "content": raw}], system=OCR_FIX_SYSTEM)
    return raw if isinstance(result, Refusal) else result.text.strip()


async def read_document(doc: pymupdf.Document, pages: list[PageText], llm: LLMClient, *,
                        limit: asyncio.Semaphore,
                        on_page: Callable[[int], Awaitable[None]] | None = None,
                        local_ocr: Callable[[pymupdf.Page], str | None] | None = None) -> tuple[list[str], int]:
    """Chữ của từng trang (thứ tự trang). Trang có lớp chữ dùng được → lấy thẳng; còn lại → OCR.

    `local_ocr` (OCR trên máy, None nếu không có) → LLM chỉ sửa chữ; không có → LLM đọc ảnh trang.

    Trả về (texts, số trang phải OCR). `on_page(done)` được gọi mỗi khi xong thêm một trang.
    """
    texts = [p.text if p.usable else "" for p in pages]
    done = sum(p.usable for p in pages)
    if on_page:
        await on_page(done)

    async def ocr(p: PageText):
        nonlocal done
        page = doc[p.number - 1]
        started = time.perf_counter()
        raw = await asyncio.to_thread(local_ocr, page) if local_ocr else None
        local_s = time.perf_counter() - started
        async with limit:
            texts[p.number - 1] = await (fix_ocr_text(llm, raw) if raw is not None else ocr_page(llm, page))
        done += 1
        log.info("ocr page", extra={"page": p.number, "source": "local" if raw is not None else "llm",
                                    "local_s": round(local_s, 2), "raw_chars": len(raw or ""),
                                    "chars": len(texts[p.number - 1]), "done": done, "total": len(pages)})
        if on_page:
            await on_page(done)

    unusable = [p for p in pages if not p.usable]
    await asyncio.gather(*(ocr(p) for p in unusable))
    return texts, len(unusable)


FIGURE_SYSTEM = (
    "Bạn ghi lại DỮ KIỆN của một hình trong sách giáo khoa (lớp 1-12) để giáo viên kiểm tra và làm tri thức gốc cho "
    "gia sư LUSIA dạy học sinh khiếm thị; LUSIA sẽ tự diễn đạt lại khi giảng, nên KHÔNG viết lời giảng, không 'em hãy "
    "tưởng tượng'. Mô tả ĐẦY ĐỦ và CHÍNH XÁC bằng tiếng Việt: hình là gì và chú thích/số hình nếu có; các thành phần "
    "(trục, đường, điểm, cạnh, góc, ô bảng) với nhãn; số liệu và toạ độ đọc được; quan hệ giữa chúng (cắt nhau, song "
    "song, vuông góc, nằm trên, bên trái/phải, phía trên/dưới); xu hướng; và hình minh họa điều gì cho bài học. Chỉ ghi "
    "điều thấy được trong hình, chi tiết nào không đọc rõ thì nói rõ là không chắc. Viết số và phép toán bằng lời "
    "('y bằng hai x cộng một', không 'y = 2x + 1'). Phân loại hình: graph, diagram, map, photo, table, hoặc "
    "decorative nếu chỉ để trang trí (linh vật, nhân vật hoạt hình, biểu tượng, dải tiêu đề) hoặc là khung/bảng chỉ "
    "chứa chữ đã có trong trang (bảng khái niệm, hộp ghi nhớ) - phần chữ đó đã được lấy riêng."
)
NOTATION = re.compile(r"[=^\\$]|[a-z0-9]\s*[+*/]\s*[a-z0-9]|\d\s*-\s*\d")  # ký hiệu toán sót trong mô tả "để đọc"


class FigureDescription(BaseModel):
    kind: Literal["graph", "diagram", "map", "photo", "table", "decorative"]
    description: str


async def describe_figure(llm: LLMClient, png: bytes, page_text: str = "",
                          route: str = "vision_offline") -> FigureDescription | None:
    """Dữ kiện của hình (tri thức gốc để giáo viên duyệt); None nếu chỉ để trang trí. Còn ký hiệu → viết lại một lần."""
    messages = [{"role": "user", "content": [
        image_block(png, "image/png"),
        {"type": "text", "text": f"Chữ trên trang quanh hình (để hiểu ngữ cảnh):\n{page_text[:1500]}"}]}]
    for attempt in range(2):
        result = await llm.complete(route, messages, system=FIGURE_SYSTEM, schema=FigureDescription)
        if isinstance(result, Refusal):
            raise ToolError(f"figure description refused ({result.category or result.explanation})")
        figure = result.parsed
        if figure.kind == "decorative":
            return None
        if attempt == 1 or not NOTATION.search(figure.description):
            return figure  # vẫn còn ký hiệu sau lần 2: giữ, bộ chuẩn hóa giọng đọc (voice-loop) xử lý nốt
        messages += [{"role": "assistant", "content": figure.model_dump_json()},
                     {"role": "user", "content": "Viết lại mô tả bằng lời để đọc thành tiếng, không dùng ký hiệu "
                                                 "như =, +, ^, phân số dạng a/b."}]
    raise AssertionError("unreachable")
