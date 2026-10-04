"""Đọc PDF: kiểm tra file, lấy chữ từng trang và đánh giá lớp chữ có dùng được không, render trang/vùng ra PNG."""
from dataclasses import dataclass

import pymupdf

MIN_PAGE_CHARS = 30
RENDER_DPI = 200
# Ký tự "rác" khi PDF dùng font TCVN3/VNI cũ: chữ Việt hiện thành ký tự Latin-1 lạ (vd "Hµm sè bËc nhÊt")
LEGACY_ARTIFACTS = set("¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿ÆËÌÎÏÐÑÒÓÖ×ØÛÜÞßåæçëîïðñö÷øûüþÿ")
# Chữ chỉ có trong tiếng Việt (ngoài Latin-1): văn bản Unicode tiếng Việt gần như luôn có
VIETNAMESE_ONLY = set("ăằắẳẵặđơờớởỡợưừứửữựạảấầẩẫậẹẻẽếềểễệỉịọỏốồổỗộụủỳỵỷỹĩũ"
                      "ĂẰẮẲẴẶĐƠỜỚỞỠỢƯỪỨỬỮỰẠẢẤẦẨẪẬẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỤỦỲỴỶỸĨŨ")


class PdfError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    number: int        # 1-based, theo chỉ số trang PDF
    text: str
    usable: bool
    reason: str = ""   # vì sao không dùng được lớp chữ


def open_pdf(data: bytes, max_pages: int) -> pymupdf.Document:
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise PdfError("file is not a PDF")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PdfError(f"unreadable PDF: {e}") from None
    if doc.needs_pass:
        doc.close()
        raise PdfError("PDF is encrypted")
    if doc.page_count == 0:
        doc.close()
        raise PdfError("PDF has no pages")
    if doc.page_count > max_pages:
        count = doc.page_count
        doc.close()
        raise PdfError(f"PDF has {count} pages (limit {max_pages})")
    return doc


def has_visual_content(page: pymupdf.Page) -> bool:
    return bool(page.get_images()) or bool(page.get_drawings())


def text_usability(text: str, visual: bool) -> tuple[bool, str]:
    chars = [c for c in text if not c.isspace()]
    if len(chars) < MIN_PAGE_CHARS:
        return (False, "no text layer") if visual else (True, "")  # trang trống thật thì không cần OCR
    letters = [c for c in chars if c.isalpha()]
    artifacts = sum(c in LEGACY_ARTIFACTS for c in letters + [c for c in chars if not c.isalnum()])
    vietnamese = sum(c in VIETNAMESE_ONLY for c in letters)
    if letters and artifacts / len(letters) > 0.02 and vietnamese == 0:
        return False, "legacy Vietnamese font encoding"
    return True, ""


def page_texts(doc: pymupdf.Document) -> list[PageText]:
    result = []
    for page in doc:
        text = page.get_text("text", sort=True)
        usable, reason = text_usability(text, has_visual_content(page))
        result.append(PageText(page.number + 1, text, usable, reason))
    return result


def render_png(page: pymupdf.Page, clip: pymupdf.Rect | None = None, dpi: int = RENDER_DPI) -> bytes:
    return page.get_pixmap(clip=clip, dpi=dpi).tobytes("png")


def bookmarks(doc: pymupdf.Document) -> list[tuple[int, str, int]]:
    """[(level, title, page 1-based)] - bỏ mục trỏ ra ngoài tài liệu."""
    return [(lvl, title.strip(), page) for lvl, title, page, *_ in doc.get_toc(simple=False)
            if 1 <= page <= doc.page_count and title.strip()]
