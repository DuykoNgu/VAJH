"""Tool Layer — các tool Orchestrator gọi cho agent:

search_knowledge, get_student_profile, save_learning_result, generate_quiz,
grade_answer, describe_image, read_document, create_learning_plan, send_teacher_report

Đã có: read_document (đọc PDF, OCR trang không có lớp chữ), describe_figure (mô tả hình để đọc thành tiếng).
"""
import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Literal

import pymupdf
from pydantic import BaseModel

from app.ai.llm import LLMClient, Refusal, image_block
from app.ingestion.pdf import PageText, render_png

OCR_PROMPT = (
    "Chép lại CHÍNH XÁC toàn bộ chữ trên trang sách giáo khoa này, theo thứ tự đọc, giữ nguyên tiếng Việt có dấu "
    "và xuống dòng giữa các đoạn. Công thức viết dạng văn bản thường (ví dụ: y = 2x + 1). Không mô tả hình, không "
    "thêm lời giải thích. Nếu trang không có chữ, trả về chuỗi rỗng."
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


async def read_document(doc: pymupdf.Document, pages: list[PageText], llm: LLMClient, *,
                        limit: asyncio.Semaphore,
                        on_page: Callable[[int], Awaitable[None]] | None = None) -> tuple[list[str], int]:
    """Chữ của từng trang (thứ tự trang). Trang có lớp chữ dùng được → lấy thẳng; còn lại → OCR bằng LLM.

    Trả về (texts, số trang phải OCR). `on_page(done)` được gọi mỗi khi xong thêm một trang.
    """
    texts = [p.text if p.usable else "" for p in pages]
    done = sum(p.usable for p in pages)
    if on_page:
        await on_page(done)

    async def ocr(p: PageText):
        nonlocal done
        async with limit:
            texts[p.number - 1] = await ocr_page(llm, doc[p.number - 1])
        done += 1
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
    "decorative nếu chỉ để trang trí."
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
