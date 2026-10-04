import pytest

from app.voice.normalize import normalize_for_speech, number_words


@pytest.mark.parametrize("text, spoken", [
    ("y = 2x + 1", "y bằng hai x cộng một"),
    ("Hàm số y = ax + b với a khác 0.", "Hàm số y bằng a x cộng b với a khác 0."),
    ("Cho y = 3x - 2.", "Cho y bằng ba x trừ hai."),
    ("Tính x^2 + 4", "Tính x bình phương cộng bốn"),
    ("12 : 4 = 3", "mười hai chia bốn bằng ba"),
    ("2 × 15 = 30", "hai nhân mười lăm bằng ba mươi"),
])
def test_maths_read_aloud(text, spoken):
    assert normalize_for_speech(text) == spoken


@pytest.mark.parametrize("text", [
    "Hôm nay là ngày 2026-10-04.",
    "Đồ thị cắt trục tung tại điểm có tung độ bằng 1.",
    "Em làm tốt lắm, mình chuyển sang câu tiếp theo nhé.",
    "Xem trang 45-50 trong sách.",
])
def test_prose_and_dates_untouched(text):
    assert normalize_for_speech(text) == text


@pytest.mark.parametrize("n, words", [(0, "không"), (10, "mười"), (11, "mười một"), (15, "mười lăm"),
                                      (21, "hai mươi mốt"), (24, "hai mươi tư"), (25, "hai mươi lăm"),
                                      (100, "một trăm"), (105, "một trăm lẻ năm"), (110, "một trăm mười"),
                                      (999, "chín trăm chín mươi chín")])
def test_number_words(n, words):
    assert number_words(n) == words
