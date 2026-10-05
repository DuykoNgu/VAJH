"""Chuẩn bị chữ cho giọng đọc (speakable): bỏ ký hiệu trích dẫn [n] → gộp số phân nhóm "2 028" → đơn vị đo
("12 nghìn đồng/kg", "5 cm2") → công thức thành lời ("y = 2x + 1" → "y bằng hai x cộng một") → bộ chuẩn hoá tiếng Việt
của ZeroTTS (số, số thập phân, ngày giờ, %, viết tắt; model không tự gọi nó).

normalize_for_speech chỉ đổi bên trong cụm công thức (có =, toán tử hoặc biến chữ cái); văn xuôi giữ nguyên.
"""
import re

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
OPERATORS = {"=": "bằng", "+": "cộng", "-": "trừ", "−": "trừ", "*": "nhân", "×": "nhân", "·": "nhân",
             "/": "chia", ":": "chia"}
POWERS = {"2": "bình phương", "3": "lập phương"}
UNIT = r"(?:\d+,\d+|[A-Za-z0-9()])"  # số thập phân dấu phẩy (4,5) là MỘT đơn vị, không tách
TOKEN = rf"{UNIT}+(?:\^\d+{UNIT}*)*"  # nhiều luỹ thừa trong một hạng tử: 7y^3z^2, x^3y^2z
# ":" là phép chia khi cách đều hai bên ("6 : 2") hoặc liền hai bên ("a:b"); "Câu 1: Hàm số" là dấu câu, giữ nguyên
OP = r"(?:\s*[=+\-−*×·/]\s*|\s+:\s+|:)"
POWERED = rf"{UNIT}*\^\d+{UNIT}*(?:\^\d+{UNIT}*)*"  # hạng tử đứng riêng có luỹ thừa: x^3y^2z
SIGN = r"(?:(?<![A-Za-z0-9)])[-−]\s*)?"  # dấu trừ đứng đầu: -7y^3z^2
EXPRESSION = re.compile(rf"{SIGN}{TOKEN}(?:{OP}{TOKEN})+|{SIGN}{POWERED}")


def number_words(n: int) -> str:
    """0-999 bằng chữ (mười lăm, hai mươi mốt, hai mươi tư, một trăm lẻ năm)."""
    if n < 10:
        return DIGITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        head = "mười" if tens == 1 else f"{DIGITS[tens]} mươi"
        if unit == 0:
            return head
        tail = {1: "mốt" if tens > 1 else "một", 4: "tư" if tens > 1 else "bốn", 5: "lăm"}.get(unit, DIGITS[unit])
        return f"{head} {tail}"
    hundreds, rest = divmod(n, 100)
    head = f"{DIGITS[hundreds]} trăm"
    if rest == 0:
        return head
    return f"{head} lẻ {DIGITS[rest]}" if rest < 10 else f"{head} {number_words(rest)}"


def _say_number(text: str) -> str:
    """12 → mười hai; 4,5 → bốn phẩy năm; 0,05 → không phẩy không năm; số dài giữ nguyên cho TTS tự đọc."""
    whole, _, decimal = text.partition(",")
    spoken = number_words(int(whole)) if len(whole) <= 3 else whole
    if not decimal:
        return spoken
    tail = " ".join(DIGITS[int(d)] for d in decimal) if decimal.startswith("0") or len(decimal) > 3 \
        else number_words(int(decimal))
    return f"{spoken} phẩy {tail}"


def _say_token(token: str) -> str:
    """2x → hai x, ax → a x, 7y^3z^2 → bảy y lập phương z bình phương (mỗi luỹ thừa thuộc thừa số ngay trước nó)."""
    words = []
    for unit, power in re.findall(r"(\d+,\d+|\d+|[A-Za-z]|[()])(?:\^(\d+))?", token):
        word = _say_number(unit) if unit[0].isdigit() else unit
        words.append(f"{word} {POWERS.get(power) or f"mũ {_say_number(power)}"}" if power else word)
    return " ".join(words)


def _say_expression(match: re.Match) -> str:
    expr = match.group()
    if not re.search(r"[A-Za-z=^]", expr):  # chỉ số và gạch nối (ngày tháng, số trang) → không phải công thức
        return expr
    parts = re.split(r"\s*([=+\-−*×·/:])\s*", expr)
    words = [OPERATORS[p] if p in OPERATORS else _say_token(p) for p in parts if p]
    return " ".join(words)


def normalize_for_speech(text: str) -> str:
    return re.sub(r"\s+", " ", EXPRESSION.sub(_say_expression, text)).strip()


CITATION = re.compile(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]")  # "[2]", "[1, 3]": số đoạn sách, không phải lời nói
GROUPED = re.compile(r"(?<![\d,.])(\d{1,3})((?: \d{3})+)(?![\d,])")  # 2 028, 1 000 000 (phân nhóm bằng dấu cách)
UNITS = {"km2": "ki lô mét vuông", "dm2": "đề xi mét vuông", "cm2": "xăng ti mét vuông", "mm2": "mi li mét vuông",
         "m2": "mét vuông", "dm3": "đề xi mét khối", "cm3": "xăng ti mét khối", "m3": "mét khối", "km": "ki lô mét",
         "dm": "đề xi mét", "cm": "xăng ti mét", "mm": "mi li mét", "m": "mét", "kg": "ki lô gam", "g": "gam",
         "ml": "mi li lít", "l": "lít", "ha": "héc ta"}
_UNIT = "|".join(sorted(UNITS, key=len, reverse=True))
AFTER_NUMBER = re.compile(rf"(?<=\d)\s?({_UNIT})(?![\w])")  # chỉ khi đứng ngay sau số: "5 m" chứ không phải "mét"
PER_UNIT = re.compile(rf"/\s?({_UNIT}|h|giờ)(?![\w])")       # "đồng/kg" → "đồng mỗi ki lô gam", "km/h"


def _vi_normalize(text: str) -> str:
    try:
        from zerotts import normalize_vi_text
    except ImportError:  # môi trường không cài ZeroTTS: giữ chữ số
        return text
    return normalize_vi_text(text)


def speakable(text: str) -> str:
    """Chữ đưa vào TTS (xem docstring đầu file)."""
    text = CITATION.sub("", text)
    text = GROUPED.sub(lambda m: m.group(1) + m.group(2).replace(" ", ""), text)
    text = text.replace("²", "2").replace("³", "3")
    text = PER_UNIT.sub(lambda m: " mỗi " + UNITS.get(m.group(1), "giờ"), text)
    text = AFTER_NUMBER.sub(lambda m: " " + UNITS[m.group(1)], text)
    return re.sub(r"\s+", " ", _vi_normalize(normalize_for_speech(text))).strip()
