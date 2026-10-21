"""Gợi ý câu dẫn mở đầu bài (câu nói nổi tiếng, câu chuyện có thật).

Chỉ là GỢI Ý cho Tutor: hợp thì dùng nguyên văn, không thì Tutor tự nghĩ câu dẫn khác để các bài đa dạng.
"""
import hashlib
from dataclasses import dataclass
from uuid import UUID

from app.features.documents.ingestion.lessons import normalize


@dataclass(frozen=True)
class Hook:
    id: str
    spoken: str              # câu đọc nguyên văn khi mở đầu bài
    subjects: frozenset[str]  # rỗng = dùng được cho mọi môn
    topics: tuple[str, ...] = ()  # từ khóa (không dấu) trong tên bài


SCIENCE = frozenset({"vat_ly", "khtn", "hoa_hoc", "sinh_hoc"})
MATH = frozenset({"toan"})

HOOKS: tuple[Hook, ...] = (
    Hook("descartes", "Nhà toán học René Descartes là người nghĩ ra cách dùng hai trục số để xác định vị trí mỗi điểm. "
                      "Đó chính là nền móng của đồ thị hàm số.", MATH, ("do thi", "toa do", "truc")),
    Hook("euclid", "Nhà toán học Euclid từng nói: “Không có con đường hoàng gia nào dẫn đến hình học.”", MATH,
         ("hinh", "tam giac", "goc", "duong tron", "tu giac")),
    Hook("galileo", "Nhà khoa học Galileo Galilei từng nói: “Cuốn sách lớn của vũ trụ được viết bằng ngôn ngữ của "
                    "toán học.”", MATH | SCIENCE),
    Hook("gauss", "Nhà toán học Carl Friedrich Gauss từng nói: “Toán học là nữ hoàng của các khoa học.”", MATH),
    Hook("euler", "Nhà toán học Leonhard Euler về già gần như mất hẳn thị lực. Nhưng ông vẫn tiếp tục làm toán bằng "
                  "trí nhớ và trí tưởng tượng.", MATH),
    Hook("saunderson", "Nicholas Saunderson bị mù từ khi còn nhỏ. Nhưng ông đã trở thành giáo sư toán học ở Đại học "
                       "Cambridge.", MATH),
    Hook("archimedes", "Nhà khoa học Archimedes từng nói: “Hãy cho tôi một điểm tựa, tôi sẽ nâng cả Trái Đất.”",
         SCIENCE, ("don bay", "luc", "can bang", "diem tua")),
    Hook("einstein", "Nhà khoa học Albert Einstein từng nói: “Trí tưởng tượng quan trọng hơn kiến thức.”", frozenset()),
    Hook("keller", "Bà Helen Keller, người không nhìn thấy và không nghe thấy, từng viết: “Những điều tốt đẹp nhất trên "
                   "đời không thể nhìn thấy, thậm chí không thể chạm vào. Chúng phải được cảm nhận bằng trái tim.”",
         frozenset()),
)


def suggest_hooks(subject: str | None, lesson_title: str, lesson_id: UUID, k: int = 3,
                  topical_only: bool = False) -> list[Hook]:
    """Tối đa k gợi ý: đúng chủ đề bài → đúng môn → câu chung; xoay vòng theo bài để các bài nhận gợi ý khác nhau.
    topical_only: chỉ câu đúng chủ đề bài (câu chung chung làm bài giảng lan man)."""
    title = normalize(lesson_title)
    topical = [h for h in HOOKS if (not h.subjects or subject in h.subjects) and any(t in title for t in h.topics)]
    if topical_only:
        return topical[:k]
    by_subject = [h for h in HOOKS if subject in h.subjects and h not in topical]
    general = [h for h in HOOKS if not h.subjects and h not in topical]
    shift = int(hashlib.sha256(str(lesson_id).encode()).hexdigest(), 16)
    rotated = [g[shift % len(g):] + g[:shift % len(g)] if g else [] for g in (topical, by_subject, general)]
    return [h for group in rotated for h in group][:k]
