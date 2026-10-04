"""Sinh PDF cho test bằng PyMuPDF (không commit PDF thật - bản quyền SGK).

insert_htmlbox dùng font dự phòng nên tiếng Việt có dấu hiển thị và trích xuất đúng.
"""
import pymupdf

A4 = pymupdf.paper_rect("a4")  # 595 x 842 pt
TEXT_BOX = pymupdf.Rect(50, 50, 545, 400)

BAI1 = ("Bài 1. Hàm số bậc nhất\n\nHàm số bậc nhất là hàm số được cho bởi công thức y = ax + b, trong đó a và b là "
        "các số cho trước và a khác 0.\n\nVí dụ: y = 2x + 1 là một hàm số bậc nhất với a = 2 và b = 1.")
BAI2 = ("Bài 2. Đồ thị của hàm số bậc nhất\n\nĐồ thị của hàm số y = ax + b là một đường thẳng cắt trục tung tại "
        "điểm có tung độ bằng b.\n\nKhi a dương, đường thẳng đi lên từ trái sang phải.")
TCVN3 = "Bµi 1. Hµm sè bËc nhÊt\n\nHµm sè bËc nhÊt lµ hµm sè ®­îc cho bëi c«ng thøc y = ax + b."


def _html(text: str) -> str:
    paras = [p.replace("\n", "<br/>") for p in text.split("\n\n")]
    return "".join(f"<p>{p}</p>" for p in paras)


def add_text_page(doc, text: str) -> pymupdf.Page:
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_htmlbox(TEXT_BOX, _html(text))
    return page


def png(width=300, height=200, color=(200, 60, 60)) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.set_rect(pix.irect, color)
    return pix.tobytes("png")


def add_graph(page, origin=(300, 700), size=200) -> pymupdf.Rect:
    """Đồ thị y = 2x + 1 vẽ bằng đường vector + nhãn trục; trả về vùng hình."""
    ox, oy = origin
    half = size / 2
    page.draw_line((ox - half, oy), (ox + half, oy), width=1.2)          # trục hoành
    page.draw_line((ox, oy + half * 0.4), (ox, oy - half), width=1.2)   # trục tung
    page.draw_line((ox - half * 0.6, oy + half * 0.3), (ox + half * 0.4, oy - half * 0.9), width=2)  # y = 2x + 1
    page.insert_text((ox + half + 4, oy + 4), "x", fontsize=10)
    page.insert_text((ox + 4, oy - half - 4), "y", fontsize=10)
    page.insert_text((ox - 10, oy + 12), "O", fontsize=10)
    page.insert_text((ox + 4, oy - 22), "1", fontsize=10)
    return pymupdf.Rect(ox - half, oy - half, ox + half + 10, oy + half * 0.4)


def to_bytes(doc) -> bytes:
    data = doc.tobytes()
    doc.close()
    return data


def lessons_pdf() -> bytes:
    """7 trang, bookmark: Bài 1 (trang 2-4), Bài 2 (trang 5-7). Trang 6 có đồ thị vector."""
    doc = pymupdf.open()
    add_text_page(doc, "Toán 8 - Tập 2\n\nSách giáo khoa")
    add_text_page(doc, BAI1)
    add_text_page(doc, "Luyện tập: cho hàm số y = 3x - 2. Tìm hệ số a và b.")
    add_text_page(doc, "Bài tập về nhà: lấy thêm hai ví dụ về hàm số bậc nhất.")
    add_text_page(doc, BAI2)
    page = add_text_page(doc, "Hình 1 dưới đây là đồ thị của hàm số y = 2x + 1.")
    add_graph(page)
    add_text_page(doc, "Ghi nhớ: đồ thị hàm số bậc nhất luôn là một đường thẳng.")
    doc.set_toc([[1, "Bài 1. Hàm số bậc nhất", 2], [1, "Bài 2. Đồ thị của hàm số bậc nhất", 5]])
    return to_bytes(doc)


def toc_pdf() -> bytes:
    """Không bookmark; trang 2 là MỤC LỤC với số trang in lệch 2 so với chỉ số PDF (Bài 1 in trang 1 = PDF trang 3)."""
    doc = pymupdf.open()
    add_text_page(doc, "Toán 8 - Tập 2")
    add_text_page(doc, "MỤC LỤC\n\nBài 1. Hàm số bậc nhất ........ 1\nBài 2. Đồ thị của hàm số bậc nhất ........ 3")
    add_text_page(doc, BAI1)
    add_text_page(doc, "Luyện tập: cho hàm số y = 3x - 2.")
    add_text_page(doc, BAI2)
    add_text_page(doc, "Ghi nhớ: đồ thị là một đường thẳng.")
    return to_bytes(doc)


def plain_pdf(pages=3) -> bytes:
    """Tài liệu ngắn không cấu trúc (phiếu học tập)."""
    doc = pymupdf.open()
    for i in range(1, pages + 1):
        add_text_page(doc, f"Phiếu học tập trang {i}.\n\nEm hãy đọc kỹ đề bài số {i} và trả lời câu hỏi.")
    return to_bytes(doc)


def figures_pdf() -> bytes:
    """Trang 1: đồ thị vector + icon nhỏ + khung viền trang. Trang 2: ảnh PNG nhúng. Trang 3: chữ thường."""
    doc = pymupdf.open()
    page = add_text_page(doc, "Quan sát hình vẽ sau.")
    add_graph(page)
    page.draw_rect(pymupdf.Rect(60, 420, 70, 430), color=(0, 0, 0), fill=(0, 0, 0))   # icon 10x10 (~0.02%)
    page.draw_rect(pymupdf.Rect(15, 15, A4.width - 15, A4.height - 15), width=0.8)    # khung viền trang
    page = add_text_page(doc, "Ảnh minh họa thí nghiệm.")
    page.insert_image(pymupdf.Rect(150, 450, 450, 650), stream=png())
    add_text_page(doc, "Trang này chỉ có chữ.")
    return to_bytes(doc)


def special_pages_pdf() -> bytes:
    """Trang 1: chữ chuẩn. Trang 2: trống. Trang 3: lỗi font TCVN3. Trang 4: chỉ có ảnh (trang scan)."""
    doc = pymupdf.open()
    add_text_page(doc, BAI1)
    doc.new_page(width=A4.width, height=A4.height)
    add_text_page(doc, TCVN3)
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_image(page.rect, stream=png(600, 850, (240, 240, 230)))
    return to_bytes(doc)


def encrypted_pdf() -> bytes:
    doc = pymupdf.open()
    add_text_page(doc, "Bí mật")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    doc.close()
    return data


def many_pages_pdf(pages: int) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    return to_bytes(doc)


def three_figures_pdf() -> bytes:
    """3 trang, mỗi trang một hình: đồ thị, ảnh, đồ thị."""
    doc = pymupdf.open()
    add_graph(add_text_page(doc, "Hình 1 là đồ thị của hàm số y = 2x + 1."))
    add_text_page(doc, "Hình 2 là ảnh chụp thí nghiệm trong phòng học.").insert_image(
        pymupdf.Rect(150, 450, 450, 650), stream=png())
    add_graph(add_text_page(doc, "Hình 3 là đồ thị của hàm số y = 2x + 1 lần nữa."))
    return to_bytes(doc)
