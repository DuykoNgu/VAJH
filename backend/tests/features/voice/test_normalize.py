import pytest

from app.features.voice.normalize import normalize_for_speech, number_words


@pytest.mark.parametrize("text, spoken", [
    ("y = 2x + 1", "y bằng hai x cộng một"),
    ("Hàm số y = ax + b với a khác 0.", "Hàm số y bằng a x cộng b với a khác 0."),
    ("Cho y = 3x - 2.", "Cho y bằng ba x trừ hai."),
    ("Tính x^2 + 4", "Tính x bình phương cộng bốn"),
    ("12 : 4 = 3", "mười hai chia bốn bằng ba"),
    ("2 × 15 = 30", "hai nhân mười lăm bằng ba mươi"),
    ("Phần 1: x : y", "Phần 1: x chia y"),
    ("a:b", "a chia b"),
    ("Ví dụ: 2x + 3x.", "Ví dụ: hai x cộng ba x."),
    ("-7y^3z^2", "trừ bảy y lập phương z bình phương"),
    ("x^3y^2z", "x lập phương y bình phương z"),
    ("Thu gọn 4,5x^2y", "Thu gọn bốn phẩy năm x bình phương y"),
    ("2,5x - 0,05", "hai phẩy năm x trừ không phẩy không năm"),
    ("-x^6y", "trừ x mũ sáu y"),
    ("Phân số 3/4", "Phân số ba phần bốn"),
    ("Tính 3/4 + 1/2", "Tính ba phần bốn cộng một phần hai"),
    ("3/4 = 0,75", "ba phần bốn bằng không phẩy bảy mươi lăm"),
    ("4,5 x 2 = 9", "bốn phẩy năm nhân hai bằng chín"),
    ("Tỉ số 3 : 5", "Tỉ số ba chia năm"),
    ("x/2 = 3", "x chia hai bằng ba"),
])
def test_maths_read_aloud(text, spoken):
    assert normalize_for_speech(text) == spoken


@pytest.mark.parametrize("text", [
    "Hôm nay là ngày 2026-10-04.",
    "Đồ thị cắt trục tung tại điểm có tung độ bằng 1.",
    "Em làm tốt lắm, mình chuyển sang câu tiếp theo nhé.",
    "Xem trang 45-50 trong sách.",
    "Câu 1: Hàm số bậc nhất?",            # dấu hai chấm sau nhãn là dấu câu, không phải phép chia
    "Ý 1: Đơn thức là gì.",
    "Bài 3: Phép cộng và phép trừ đa thức.",
    "Lúc 7:30 em đi học.",
    "Ngày 2/9 là ngày Quốc khánh.",
    "Hạn nộp 12/10/2026.",
])
def test_prose_and_dates_untouched(text):
    assert normalize_for_speech(text) == text


@pytest.mark.parametrize("n, words", [(0, "không"), (10, "mười"), (11, "mười một"), (15, "mười lăm"),
                                      (21, "hai mươi mốt"), (24, "hai mươi tư"), (25, "hai mươi lăm"),
                                      (100, "một trăm"), (105, "một trăm lẻ năm"), (110, "một trăm mười"),
                                      (999, "chín trăm chín mươi chín")])
def test_number_words(n, words):
    assert number_words(n) == words


@pytest.mark.parametrize("text, spoken", [
    ("Chữ số 2 đầu tiên có giá trị 2 000. [2]", "Chữ số hai đầu tiên có giá trị hai nghìn."),
    ("Số 2 028 và 1 000 000", "Số hai nghìn không trăm hai mươi tám và một triệu"),
    ("Giá 12 nghìn đồng/kg, xe chạy 60 km/h.", "Giá mười hai nghìn đồng mỗi ki lô gam, xe chạy sáu mươi ki lô mét mỗi giờ."),
    ("Diện tích 20 m2 và 8 cm². Cao 1,5 m.", "Diện tích hai mươi mét vuông và tám xăng ti mét vuông. Cao một phẩy năm mét."),
    ("Em đi 5 lần, mỗi lần 2 giờ.", "Em đi năm lần, mỗi lần hai giờ."),               # "lần", "giờ" không phải đơn vị viết tắt
    ("Câu 1: Hàm số y = 2x + 1.", "Câu một: Hàm số y bằng hai x cộng một."),
])
def test_speakable_text_for_tts(text, spoken):
    from app.features.voice.normalize import speakable

    assert speakable(text) == spoken
