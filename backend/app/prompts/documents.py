"""Prompt của luồng nạp tài liệu: OCR, mô tả hình, mục lục, dàn ý giảng."""

# ---- OCR trang scan ----
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


# ---- Mô tả hình (Vision) ----
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
FIGURE_CONTEXT_CHARS = 1500
FIGURE_REWRITE = ("Viết lại mô tả bằng lời để đọc thành tiếng, không dùng ký hiệu "
                  "như =, +, ^, phân số dạng a/b.")


def figure_context(page_text: str) -> str:
    return f"Chữ trên trang quanh hình (để hiểu ngữ cảnh):\n{page_text[:FIGURE_CONTEXT_CHARS]}"


# ---- Mục lục → danh sách bài ----
TOC_PROMPT = (
    "Dưới đây là chữ của các trang đầu một tài liệu học tập. Nếu có MỤC LỤC, liệt kê các bài học theo thứ tự: tiêu đề "
    "đầy đủ đúng như in và số trang in bên cạnh. Lấy các bài học và các buổi ôn riêng ('Luyện tập chung', 'Bài tập "
    "cuối chương', 'Ôn tập'); bỏ tên chương và mục nhỏ bên trong bài. Không có mục lục thì trả về danh sách rỗng."
)


def toc_user(first_pages: str) -> str:
    return f"{TOC_PROMPT}\n\n{first_pages}"


# ---- Dàn ý giảng cho từng bài ----
OUTLINE_SYSTEM = (
    "Bạn soạn DÀN Ý GIẢNG cho MỘT bài trong sách giáo khoa, để gia sư giảng bằng lời cho học sinh khiếm thị. Đầu vào "
    "là các đoạn sách đánh số [n] theo thứ tự trang (chữ do OCR, có thể lẫn nhiễu). "
    "`points`: các Ý CHÍNH của bài theo đúng thứ tự trong sách; mỗi ý là một kiến thức cốt lõi: định nghĩa, quy tắc, "
    "tính chất, công thức hoặc cách làm. Thường 3 đến 6 ý, tối đa 8. "
    "BỎ QUA, không biến thành ý: lời giới thiệu chương; hộp 'Khái niệm, thuật ngữ' và 'Kiến thức, kĩ năng' (chỉ dùng để "
    "biết bài có những ý nào); các hoạt động HĐ (chỉ lấy kết luận mà chúng dẫn tới); lời thoại nhân vật; chữ chìm, số "
    "trang, tiêu đề lặp. Bài tập ('Luyện tập', 'Vận dụng', 'Bài tập', các câu 1.1, 1.2…) KHÔNG phải ý giảng: dùng chúng "
    "để đặt câu hỏi kiểm tra cho ý tương ứng. "
    "Mỗi ý: `title` ngắn (tối đa 8 từ, ví dụ 'Đơn thức là gì'); `content` 1 đến 3 câu NÊU THẲNG kiến thức như sách "
    "viết, kèm MỘT ví dụ cụ thể lấy từ sách; `question` MỘT câu hỏi kiểm tra ngắn về đúng ý đó, trả lời được bằng vài "
    "từ (ưu tiên chuyển từ bài luyện tập trong sách; không hỏi chung chung kiểu 'có gì giống nhau'); `answer` đáp án "
    "đúng và ngắn (tự tính lại cho chắc); `sources` các số [n] đã dùng (kể cả MÔ TẢ HÌNH nếu ý đó dựa vào hình). "
    "`opening`: tình huống hoặc bài toán mở đầu của bài nếu sách có (1 đến 2 câu, giữ các con số), rỗng nếu không có; "
    "`opening_sources`: số [n] của đoạn đó. "
    "CHỈ dùng thông tin trong các đoạn, không thêm kiến thức ngoài. Viết công thức bằng ký hiệu thường (x^2, a/b, "
    "sqrt(2)), không dùng LaTeX."
)


def outline_user(title: str, passages: list[str]) -> str:
    """passages: các đoạn đã đánh số [n] (xem outline.passages)."""
    return f"Bài: {title}\n\n" + "\n\n".join(passages)
