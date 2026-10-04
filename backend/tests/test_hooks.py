import uuid

from app.hooks import suggest_hooks

LESSON = uuid.UUID("00000000-0000-0000-0000-0000000000e1")


def ids(subject, title, lesson=LESSON):
    return [h.id for h in suggest_hooks(subject, title, lesson)]


def test_topic_suggestion_first_for_graph_lesson():
    assert ids("toan", "Bài 2. Đồ thị của hàm số bậc nhất")[0] == "descartes"


def test_geometry_topic_first():
    assert ids("toan", "Bài 5. Tam giác cân")[0] == "euclid"


def test_subject_then_general_and_at_most_three():
    math = ids("toan", "Ôn tập chương")
    assert len(math) == 3 and all(h in {"galileo", "gauss", "euler", "saunderson", "descartes", "euclid"} for h in math)
    assert set(ids("lich_su", "Bài 1. Văn Lang")) == {"einstein", "keller"}


def test_suggestions_rotate_across_lessons():
    firsts = {ids("toan", "Ôn tập chương", uuid.uuid4())[0] for _ in range(40)}
    assert len(firsts) > 1
