"""Đọc công thức thành lời trước khi TTS: "y = 2x + 1" → "y bằng hai x cộng một".

Chỉ đổi bên trong cụm công thức (có =, toán tử hoặc biến chữ cái); văn xuôi và ngày tháng (2026-10-04) giữ nguyên.
"""
import re

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
OPERATORS = {"=": "bằng", "+": "cộng", "-": "trừ", "−": "trừ", "*": "nhân", "×": "nhân", "·": "nhân",
             "/": "chia", ":": "chia"}
POWERS = {"2": "bình phương", "3": "lập phương"}
TOKEN = r"[A-Za-z0-9()]+(?:\^\d+)?"
OP = r"\s*[=+\-−*×·/:]\s*"
EXPRESSION = re.compile(rf"{TOKEN}(?:{OP}{TOKEN})+|[A-Za-z]\^\d+")


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


def _say_token(token: str) -> str:
    base, _, power = token.partition("^")
    base = re.sub(r"(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=[A-Za-z])", " ", base)  # 2x → 2 x, ax → a x
    base = re.sub(r"\d+", lambda m: number_words(int(m.group())) if len(m.group()) <= 3 else m.group(), base)
    return f"{base} {POWERS.get(power, 'mũ ' + power)}" if power else base


def _say_expression(match: re.Match) -> str:
    expr = match.group()
    if not re.search(r"[A-Za-z=^]", expr):  # chỉ số và gạch nối (ngày tháng, số trang) → không phải công thức
        return expr
    parts = re.split(r"\s*([=+\-−*×·/:])\s*", expr)
    words = [OPERATORS[p] if p in OPERATORS else _say_token(p) for p in parts if p]
    return " ".join(words)


def normalize_for_speech(text: str) -> str:
    return re.sub(r"\s+", " ", EXPRESSION.sub(_say_expression, text)).strip()
