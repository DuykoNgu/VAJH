"""Assessment Agent: tạo quiz 3 câu từ nội dung bài, đọc câu hỏi, chấm câu trả lời bằng lời, lưu kết quả.

mode "chat" (Orchestrator chuyển tới vì học sinh muốn kiểm tra) → tạo quiz và đọc câu 1.
mode "quiz" (phiên đang có câu chưa trả lời) → chấm câu hiện tại, đọc nhận xét và câu tiếp / tổng điểm.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.agents.base import AgentResult, Handoff, TurnContext
from app.agents.tutor import LISTENING_STYLE
from app.ai.llm import LLMClient, Refusal
from app.storage import relational

LETTERS = "ABCD"
QUESTIONS = 3
LESSON_CHARS = 6000
NO_LESSON = "Em chọn một bài học trước rồi mình kiểm tra nhé."
FAILED = "Xin lỗi, mình chưa tạo được câu hỏi cho bài này. Em thử lại sau nhé."

QUIZ_SYSTEM = (
    "Bạn soạn câu hỏi trắc nghiệm kiểm tra bài cho học sinh khiếm thị; câu hỏi sẽ được ĐỌC thành tiếng. "
    f"Soạn đúng {QUESTIONS} câu, mỗi câu 3 hoặc 4 lựa chọn ngắn, CHỈ dựa trên nội dung bài được cung cấp. "
    "Viết để đọc: không dùng ký hiệu (viết 'y bằng hai x cộng một'). `correct` phải trùng nguyên văn một lựa chọn. "
    "`focus` = figure nếu câu hỏi về hình/đồ thị (dựa trên MÔ TẢ HÌNH), concept nếu về kiến thức. "
    "Nếu bài có MÔ TẢ HÌNH thì ít nhất một câu có focus figure."
)
GRADE_SYSTEM = (
    "Học sinh khiếm thị trả lời câu trắc nghiệm bằng giọng nói (có thể nói chữ cái, nội dung đáp án, hoặc cả hai; "
    "có thể sai chính tả do nhận dạng giọng nói). Xác định lựa chọn học sinh muốn chọn: `choice_index` bắt đầu từ 0, "
    "null nếu không xác định được. `feedback`: MỘT câu khích lệ ngắn, ấm áp, để đọc thành tiếng; KHÔNG nhắc lại "
    "đáp án, lựa chọn của học sinh hay lời giải thích (hệ thống tự đọc phần đó). " + LISTENING_STYLE
)


OPEN_SYSTEM = (
    "Bạn chấm câu trả lời NÓI của học sinh khiếm thị cho một câu hỏi kiểm tra ngắn (có thể sai chính tả do nhận dạng "
    "giọng nói). `score`: 1 nếu đúng ý, 0.5 nếu đúng một phần, 0 nếu sai, không biết, hoặc muốn bỏ qua ('tiếp', 'không "
    "biết'). `feedback`: MỘT câu khích lệ ngắn, ấm áp. `re_explanation`: nếu score < 1, giảng lại 1-3 câu ngắn bằng "
    "hình ảnh tưởng tượng để học sinh hiểu đáp án; nếu score = 1 để rỗng. `is_student_question` = true CHỈ khi học "
    "sinh không trả lời mà đặt câu hỏi khác hoặc ra lệnh khác (muốn làm bài kiểm tra, đổi bài...). " + LISTENING_STYLE
)


class OpenGrade(BaseModel):
    is_student_question: bool
    score: float
    feedback: str
    re_explanation: str


class QuestionDraft(BaseModel):
    prompt: str
    choices: list[str]
    correct: str
    explanation: str
    focus: Literal["concept", "figure"]


class QuizDraft(BaseModel):
    questions: list[QuestionDraft]


class Grade(BaseModel):
    choice_index: int | None
    feedback: str


def read_question(position: int, prompt: str, choices: list[str]) -> str:
    options = "; ".join(f"{LETTERS[i]}, {c}" for i, c in enumerate(choices))
    return f"Câu {position}: {prompt} {options}. Em chọn đáp án nào?"


def _valid(q: QuestionDraft) -> bool:
    return 3 <= len(q.choices) <= 4 and q.correct in q.choices and bool(q.prompt.strip())


async def _rows(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


async def current_question(session_id: UUID):
    """Câu chưa trả lời đầu tiên (quiz mới nhất trước) trong phiên, hoặc None."""
    rows = await _rows(
        "SELECT q.id, q.position, q.prompt, q.choices, q.correct_answer, q.explanation,"
        " (SELECT count(*) FROM questions WHERE quiz_id = z.id)"
        " FROM quizzes z JOIN questions q ON q.quiz_id = z.id"
        " WHERE z.session_id = %s AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.question_id = q.id)"
        " ORDER BY z.created_at DESC, q.position LIMIT 1", (session_id,))
    return rows[0] if rows else None


class AssessmentAgent:
    name = "assessment"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, ctx: TurnContext):
        if ctx.mode == "quiz":
            yield await self._answer(ctx)
        else:
            yield AgentResult(self.name, await self._start(ctx))

    async def _draft(self, material: str, has_figure: bool) -> list[QuestionDraft]:
        valid: list[QuestionDraft] = []
        for _ in range(2):  # thử lại một lần nếu thiếu câu hợp lệ hoặc thiếu câu về hình
            result = await self.llm.complete("assessment", [{"role": "user", "content": material}],
                                             system=QUIZ_SYSTEM, schema=QuizDraft)
            if isinstance(result, Refusal):
                continue
            valid = [q for q in result.parsed.questions if _valid(q)][:QUESTIONS]
            if len(valid) == QUESTIONS and (not has_figure or any(q.focus == "figure" for q in valid)):
                break
        return valid

    async def _start(self, ctx: TurnContext) -> str:
        if ctx.lesson_id is None:
            return NO_LESSON
        chunks = await _rows("SELECT kind, content FROM chunks WHERE lesson_id = %s"
                             " AND coalesce(review, 'approved') <> 'rejected' ORDER BY page, id", (ctx.lesson_id,))
        material = "\n\n".join(("MÔ TẢ HÌNH: " if kind == "figure" else "") + content
                               for kind, content in chunks)[:LESSON_CHARS]
        questions = await self._draft(material, any(kind == "figure" for kind, _ in chunks)) if chunks else []
        if len(questions) < 2:
            return FAILED
        async with relational.transaction() as conn:
            quiz_id = (await (await conn.execute(
                "INSERT INTO quizzes (student_id, lesson_id, session_id) VALUES (%s, %s, %s) RETURNING id",
                (ctx.student_id, ctx.lesson_id, ctx.session_id))).fetchone())[0]
            for position, q in enumerate(questions, 1):
                await conn.execute(
                    "INSERT INTO questions (quiz_id, position, prompt, focus, choices, correct_answer, explanation)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (quiz_id, position, q.prompt, q.focus, q.choices, q.correct, q.explanation))
        first = questions[0]
        return f"Mình kiểm tra {len(questions)} câu nhé. {read_question(1, first.prompt, first.choices)}"

    async def _answer_open(self, ctx: TurnContext, qid, prompt: str, expected: str) -> AgentResult:
        result = await self.llm.complete("assessment", [{"role": "user", "content":
                                          f"Câu hỏi: {prompt}\nCâu trả lời mong đợi: {expected}\nHọc sinh nói: {ctx.text}"}],
                                         system=OPEN_SYSTEM, schema=OpenGrade)
        if isinstance(result, Refusal):
            grade = OpenGrade(is_student_question=False, score=0, feedback="", re_explanation=expected)
        else:
            grade = result.parsed
        if grade.is_student_question:  # không phải câu trả lời → để Orchestrator xử lý, câu hỏi kiểm tra vẫn chờ
            return AgentResult(self.name, "", handoff=Handoff("orchestrator", "học sinh hỏi điều khác", {"pending": prompt}))
        score = min((0.0, 0.5, 1.0), key=lambda v: abs(v - grade.score))
        verdict = {1.0: "Đúng rồi!", 0.5: "Em trả lời đúng một phần.", 0.0: "Chưa đúng."}[score]
        text = f"{verdict} {grade.feedback}".strip()
        if score < 1 and grade.re_explanation.strip():
            text += f" {grade.re_explanation.strip()}"
        async with relational.connection() as conn:
            await conn.execute("INSERT INTO answers (question_id, answer_text, score, feedback) VALUES (%s, %s, %s, %s)",
                               (qid, ctx.text, score, text))
        return AgentResult(self.name, text)

    async def _answer(self, ctx: TurnContext) -> AgentResult:
        question = await current_question(ctx.session_id)
        qid, position, prompt, choices, correct, explanation, total = question
        if choices is None:
            return await self._answer_open(ctx, qid, prompt, correct)
        options = "\n".join(f"{i}. {LETTERS[i]}, {c}" for i, c in enumerate(choices))
        result = await self.llm.complete("assessment", [{"role": "user", "content":
                                          f"Câu hỏi: {prompt}\nCác lựa chọn:\n{options}\nHọc sinh nói: {ctx.text}"}],
                                         system=GRADE_SYSTEM, schema=Grade)
        grade = result.parsed if not isinstance(result, Refusal) else Grade(choice_index=None, feedback="")
        index = grade.choice_index
        right = index is not None and 0 <= index < len(choices) and choices[index] == correct
        letter = LETTERS[choices.index(correct)]
        verdict = "Đúng rồi!" if right else f"Chưa đúng. Đáp án đúng là {letter}, {correct}."
        feedback = f"{verdict} {grade.feedback} {explanation}".strip()
        async with relational.connection() as conn:
            await conn.execute("INSERT INTO answers (question_id, answer_text, score, feedback) VALUES (%s, %s, %s, %s)",
                               (qid, ctx.text, 1 if right else 0, feedback))
        following = await current_question(ctx.session_id)
        if following is not None and following[3] is not None:
            return AgentResult(self.name, f"{feedback} {read_question(following[1], following[2], following[3])}")
        score = (await _rows("SELECT count(*) FILTER (WHERE a.score = 1) FROM answers a JOIN questions q"
                             " ON q.id = a.question_id WHERE q.quiz_id = (SELECT quiz_id FROM questions WHERE id = %s)",
                             (qid,)))[0][0]
        return AgentResult(self.name, f"{feedback} Em đúng {score} trên {total} câu. Em muốn hỏi thêm gì về bài này không?")
