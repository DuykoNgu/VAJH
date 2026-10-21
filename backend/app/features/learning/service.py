"""Phiên học: vào bài → giảng từng phần (Tutor, Vision khi có hình) → hỏi kiểm tra → Assessment chấm → "tiếp".
Học sinh hỏi chen: Orchestrator → Knowledge → (Vision) → Tutor. Kiểm tra cuối bài: Assessment (trắc nghiệm).

Mỗi agent là module riêng theo hợp đồng chung (app/features/learning/agents/base.py); file này chỉ điều phối, lưu tin nhắn
(chỉ transcript, không lưu audio) và trả về câu trả lời đã tách câu cho TTS kèm dấu vết các agent đã chạy.
"""
import asyncio
import contextvars
import re
from dataclasses import dataclass, field, replace
from uuid import UUID

from app.config import get_settings
from app.core.ai.llm import LLMClient
from app.core.identity import UserContext
from app.core.rag.embeddings import EmbeddingClient
from app.core.storage import relational
from app.features.learning.agents import base
from app.features.learning.agents.assessment import AssessmentAgent, current_question
from app.features.learning.agents.base import (
    AgentResult,
    ChatMessage,
    Evidence,
    Registry,
    TurnContext,
    run_agent,
)
from app.features.learning.agents.knowledge import KnowledgeAgent
from app.features.learning.agents.orchestrator import OrchestratorAgent
from app.features.learning.agents.tutor import REFUSED, TutorAgent
from app.features.learning.agents.vision import VisionAgent
from app.features.learning.hooks import suggest_hooks
from app.features.learning.teaching import (
    Part,
    get_part,
    lesson_opening,
    lesson_parts,
    set_part,
    store_check_question,
)

DISCLAIMER = "Mô tả hình này chưa được thầy cô kiểm duyệt."
NEXT_PART = "Em nói tiếp để học ý tiếp theo nhé."
TO_SUMMARY = "Em nói tiếp để mình tóm tắt cả bài nhé."
OFFER_QUIZ = "Em muốn làm 3 câu kiểm tra không? Em nói kiểm tra mình nhé."
HISTORY_LIMIT = 8
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
NUMBER_WORDS = ("một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười")


def roadmap(parts: list[Part]) -> str:
    """"một, Đơn thức là gì; hai, Thu gọn đơn thức; …": báo trước lộ trình để học sinh nghe biết bài đi tới đâu."""
    return "; ".join(f"{NUMBER_WORDS[i] if i < len(NUMBER_WORDS) else i + 1}, {p.title}" for i, p in enumerate(parts))


class SessionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass
class TraceStep:
    agent: str
    summary: str


@dataclass
class Citation:
    chunk_id: int
    page: int
    kind: str


@dataclass
class TurnReply:
    answer: str
    sentences: list[str]
    trace: list[TraceStep]
    citations: list[Citation] = field(default_factory=list)
    mode: str = "chat"  # chat | teach | quiz


def build_agents(llm: LLMClient, embeddings: EmbeddingClient) -> Registry:
    """Registry riêng cho mỗi app: chép các agent đã đăng ký (stub) rồi thay bằng bản thật."""
    registry = base.registry.copy()
    registry.assert_complete()
    knowledge = KnowledgeAgent(embeddings, get_settings().rag_top_k)
    for agent in (OrchestratorAgent(llm), knowledge, VisionAgent(), TutorAgent(llm), AssessmentAgent(llm)):
        registry.replace_stub(agent)
    return registry


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


async def final(agent, ctx: TurnContext) -> AgentResult:
    result = None
    async for event in run_agent(agent, ctx):
        if isinstance(event, AgentResult):
            result = event
    return result


async def _one(sql: str, params=()):
    async with relational.connection() as conn:
        return await (await conn.execute(sql, params)).fetchone()


async def start_session(student_id: UUID, lesson_id: UUID | None) -> tuple[UUID, str | None]:
    title = None
    if lesson_id is not None:
        row = await _one("SELECT l.title, d.published_at IS NOT NULL OR d.uploaded_by = %s FROM lessons l"
                         " JOIN documents d ON d.id = l.document_id WHERE l.id = %s", (student_id, lesson_id))
        if row is None:
            raise SessionError(404, "lesson not found")
        if not row[1]:
            raise SessionError(409, "lesson is not published yet")
        title = row[0]
    row = await _one("INSERT INTO learning_sessions (student_id, lesson_id) VALUES (%s, %s) RETURNING id",
                     (student_id, lesson_id))
    return row[0], title


async def end_session(session_id: UUID) -> None:
    row = await _one("UPDATE learning_sessions SET ended_at = coalesce(ended_at, now()) WHERE id = %s RETURNING id",
                     (session_id,))
    if row is None:
        raise SessionError(404, "session not found")


async def load_session(session_id: UUID):
    row = await _one("SELECT student_id, lesson_id, ended_at FROM learning_sessions WHERE id = %s", (session_id,))
    if row is None:
        raise SessionError(404, "session not found")
    if row[2] is not None:
        raise SessionError(409, "session has ended")
    return row[0], row[1]


async def history(session_id: UUID) -> tuple[ChatMessage, ...]:
    async with relational.connection() as conn:
        rows = await (await conn.execute(
            "SELECT role, content, agent FROM (SELECT * FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT %s)"
            " recent ORDER BY id", (session_id, HISTORY_LIMIT))).fetchall()
    return tuple(ChatMessage(r[0], r[1], r[2]) for r in rows)


async def save_turn(session_id: UUID, question: str | None, agent: str, answer: str) -> None:
    async with relational.transaction() as conn:
        if question is not None:
            await conn.execute("INSERT INTO messages (session_id, role, content) VALUES (%s, 'student', %s)",
                               (session_id, question))
        await conn.execute("INSERT INTO messages (session_id, role, agent, content) VALUES (%s, 'assistant', %s, %s)",
                           (session_id, agent, answer))


CITATION = re.compile(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]")


def _reply(answer: str, trace: list[TraceStep], citations=(), mode="chat") -> TurnReply:
    answer = CITATION.sub("", answer)  # "[2]": số đoạn sách model lỡ viết vào lời nói; trích dẫn đã nằm trong citations
    return TurnReply(answer, split_sentences(answer), trace, list(citations), mode)


def drop_trailing_question(text: str) -> str:
    """Bỏ câu hỏi gợi mở cuối của Tutor khi ngay sau đó LUSIA sẽ hỏi câu khác (tránh hai câu hỏi liền nhau)."""
    sentences = split_sentences(text)
    if len(sentences) > 1 and sentences[-1].endswith("?"):
        sentences = sentences[:-1]
    return " ".join(sentences)


def _with_disclaimer(answer: str, figure: Evidence | None, cited) -> str:
    answer = answer.replace(DISCLAIMER, "").strip()
    if figure is not None and figure.unreviewed and figure.chunk_id in cited:
        answer = f"{DISCLAIMER} {answer}"  # do code thêm, không phụ thuộc model → đúng một lần
    return answer


def _citations(cited, evidence) -> list[Citation]:
    by_id = {e.chunk_id: e for e in evidence}
    return [Citation(c, by_id[c].page, by_id[c].kind) for c in cited if c in by_id]


async def begin_lesson(session_id: UUID, user: UserContext, lesson_id: UUID | None, title: str | None,
                       agents: Registry) -> TurnReply:
    """Vào bài: chào, nói bài có mấy phần, giảng luôn phần 1 (không chờ học sinh hỏi)."""
    greeting = f"Chào {user.full_name}."
    if lesson_id is None:
        reply = _reply(f"{greeting} Em giữ phím cách để hỏi mình bất cứ điều gì nhé.", [])
    else:
        parts = await lesson_parts(lesson_id)
        if not parts:
            reply = _reply(f"{greeting} Bài {title} chưa có nội dung trong sách. Em chọn bài khác nhé.", [])
        else:
            ctx = TurnContext.for_student(user, session_id=session_id, lesson_id=lesson_id, text=title)
            if parts[0].title:  # theo dàn ý: nói trước lộ trình các ý
                intro = f"{greeting} Hôm nay mình học {title}. Bài có {len(parts)} ý: {roadmap(parts)}."
            else:
                intro = f"{greeting} Hôm nay mình học {title}. Bài có {len(parts)} phần."
            reply = await teach_part(ctx, agents, parts, 1, intro=intro, opening=await lesson_opening(lesson_id),
                                     hook_ideas=await topical_hooks(lesson_id, title))
    await save_turn(session_id, None, reply.trace[-1].agent if reply.trace else "tutor", reply.answer)
    return reply


async def topical_hooks(lesson_id: UUID, title: str) -> list[str]:
    """Câu nói trong kho gợi ý CHỈ khi đúng chủ đề bài (vd. Descartes cho bài đồ thị); câu chung chung thì không dùng."""
    subject = (await _one("SELECT d.subject FROM lessons l JOIN documents d ON d.id = l.document_id WHERE l.id = %s",
                          (lesson_id,)))[0]
    return [h.spoken for h in suggest_hooks(subject, title, lesson_id, topical_only=True)]


def _opening_task(opening: str | None, hook_ideas: list[str]) -> str:
    if opening:  # tình huống mở đầu của sách: cụ thể, có số liệu, dẫn thẳng vào bài
        return (" Đây là phần MỞ ĐẦU bài. `hook`: kể NGẮN (1 đến 2 câu, giữ các con số) tình huống mở đầu của sách sau "
                f"đây rồi nói bài học sẽ giúp trả lời nó; không ẩn dụ, không kể về chương: «{opening}»")
    task = (" Đây là phần MỞ ĐẦU bài. `hook`: MỘT câu nói thẳng bài này giúp em làm được gì, cụ thể; không ẩn dụ chung "
            "chung. Nếu dùng một câu nói của người khác thì KHÔNG gán cho người thật có tên khi em không chắc họ đã nói.")
    if hook_ideas:
        task += " Có thể dùng nguyên văn một câu đúng chủ đề dưới đây:\n" + "\n".join(f"- {idea}" for idea in hook_ideas)
    return task


@dataclass
class Prepared:
    """Phần LLM của việc giảng một ý (Vision + Tutor), chưa ghi gì: soạn ngay hoặc soạn sẵn từ lượt trước."""
    taught: AgentResult
    evidence: tuple[Evidence, ...]
    figure: Evidence | None
    trace: list[TraceStep]


async def prepare_part(ctx: TurnContext, agents: Registry, parts: list[Part], number: int,
                       hook_ideas: list[str] | None = None, opening: str | None = None) -> Prepared:
    part = parts[number - 1]
    title = part.evidence[0].lesson_title or "bài học"
    trace: list[TraceStep] = []
    evidence, figure = part.evidence, None
    if part.kind == "figure":
        seen = await final(agents.get("vision"), replace(ctx, evidence=evidence))
        evidence, figure = tuple(seen.handoff.payload["evidence"]), seen.handoff.payload.get("figure")
        trace.append(TraceStep("vision", seen.handoff.reason))
        if part.title:  # theo dàn ý: kiến thức là chính, hình minh hoạ đứng sau
            evidence = tuple(e for e in evidence if e.kind == "text") + tuple(e for e in evidence if e.kind == "figure")
    if part.title:
        task = (f"Giảng ý {number} trên {len(parts)} của {title}: {part.title}. Nói thẳng kiến thức trong đoạn [1].")
        if part.question:
            task += (f" `check_question`: hỏi đúng câu sau, có thể nói lại cho dễ nghe nhưng giữ nguyên nội dung: "
                     f"«{part.question}». `expected_answer`: «{part.answer}».")
    else:
        task = f"Giảng phần {number} trên {len(parts)} của {title}."
    if hook_ideas is not None:
        task += _opening_task(opening, hook_ideas)
    taught = await final(agents.get("tutor"), replace(ctx, mode="teach", evidence=evidence, text=task))
    trace.append(TraceStep("tutor", f"giảng {'ý' if part.title else 'phần'} {number}/{len(parts)}"))
    return Prepared(taught, evidence, figure, trace)


# Soạn sẵn ý kế tiếp trong lúc học sinh trả lời câu hỏi kiểm tra → nói "tiếp" là có ngay (không chờ Tutor ~3-7 s).
# ponytail: giữ trong bộ nhớ tiến trình API; khởi động lại thì mất (ý đó được soạn bình thường), tối đa AHEAD_LIMIT.
_AHEAD: dict[tuple[UUID, int], asyncio.Task] = {}
AHEAD_LIMIT = 200


def _prepare_ahead(ctx: TurnContext, agents: Registry, parts: list[Part], number: int) -> None:
    if number > len(parts) or not get_settings().prefetch_parts:
        return
    while len(_AHEAD) >= AHEAD_LIMIT:  # phiên bỏ dở: bỏ việc soạn sẵn cũ nhất
        _AHEAD.pop(next(iter(_AHEAD))).cancel()
    # Context mới: không gắn vào trace của lượt hiện tại (trace đó đã lưu khi lượt kết thúc)
    _AHEAD[(ctx.session_id, number)] = asyncio.create_task(prepare_part(ctx, agents, parts, number),
                                                           context=contextvars.Context())


async def _take_ahead(ctx: TurnContext, number: int) -> Prepared | None:
    task = _AHEAD.pop((ctx.session_id, number), None)
    if task is None:
        return None
    try:
        return await task
    except Exception:  # soạn sẵn lỗi → soạn lại bình thường
        return None


async def teach_part(ctx: TurnContext, agents: Registry, parts: list[Part], number: int, intro: str = "",
                     hook_ideas: list[str] | None = None, preview: bool = False, opening: str | None = None,
                     prepared: Prepared | None = None) -> TurnReply:
    """preview=True: giáo viên nghe thử, không lưu câu hỏi kiểm tra và không đổi tiến độ.
    hook_ideas khác None (kể cả rỗng) = phần mở đầu bài: Tutor viết câu dẫn, ưu tiên tình huống mở đầu `opening`.
    prepared: kết quả đã soạn sẵn (không gọi lại LLM)."""
    part = parts[number - 1]
    prepared = prepared or await prepare_part(ctx, agents, parts, number, hook_ideas, opening)
    taught, evidence, figure, trace = prepared.taught, prepared.evidence, prepared.figure, list(prepared.trace)
    if taught.handoff is not None and not preview:  # Tutor chuyển câu hỏi kiểm tra cho Assessment
        await store_check_question(ctx.session_id, ctx.student_id, ctx.lesson_id, taught.handoff.payload["question"],
                                   part.answer or taught.handoff.payload["expected"],  # đáp án của dàn ý (theo sách)
                                   "figure" if part.kind == "figure" else "concept")
        trace.append(TraceStep("assessment", "đặt câu hỏi kiểm tra"))
    if not preview:
        await set_part(ctx.session_id, number)
        _prepare_ahead(ctx, agents, parts, number + 1)
    hook = taught.handoff.payload.get("hook", "") if taught.handoff and hook_ideas is not None else ""
    answer = _with_disclaimer(taught.speech_text, figure, taught.citations)
    label = f"Ý {number}: {part.title}." if part.title else f"Phần {number}."
    return _reply(" ".join(x for x in (intro, hook, label, answer) if x), trace,
                  _citations(taught.citations, evidence), "teach")


async def next_part(ctx: TurnContext, agents: Registry, trace: list[TraceStep]) -> TurnReply:
    parts = await lesson_parts(ctx.lesson_id)
    done = await get_part(ctx.session_id)
    if done < len(parts):
        prepared = await _take_ahead(ctx, done + 1)
        reply = await teach_part(ctx, agents, parts, done + 1, prepared=prepared)
        steps = [replace(t, summary=f"{t.summary} (soạn sẵn)") if prepared and t.agent == "tutor" else t
                 for t in reply.trace]
        return replace(reply, trace=trace + steps)
    if parts and parts[0].title:  # theo dàn ý: tóm tắt chính là các ý, không cần LLM, không lan man
        return _reply(f"Mình đã học hết bài. Bài có {len(parts)} ý: {roadmap(parts)}. {OFFER_QUIZ}", trace)
    # Hết bài (giảng theo đoạn): tóm tắt từ nội dung bài rồi mời làm bài kiểm tra
    evidence = tuple(e for p in parts for e in p.evidence)[:8]
    summary = await final(agents.get("tutor"), replace(
        ctx, evidence=evidence, text="Tóm tắt ngắn gọn những ý chính của cả bài cho học sinh (3-4 câu)."))
    trace.append(TraceStep("tutor", "tóm tắt bài"))
    text = drop_trailing_question(summary.speech_text)
    return _reply(f"Mình đã học hết bài. {text} {OFFER_QUIZ}", trace, _citations(summary.citations, evidence))


async def take_turn(session_id: UUID, user: UserContext, text: str, agents: Registry) -> TurnReply:
    _, lesson_id = await load_session(session_id)
    ctx = TurnContext.for_student(user, session_id=session_id, lesson_id=lesson_id, text=text,
                                  history=await history(session_id))
    question = await current_question(session_id)
    if question is None:
        reply, agent = await _chat_turn(ctx, agents)
    else:
        reply, agent = await _answer_turn(ctx, agents, question)
    await save_turn(session_id, text, agent, reply.answer)
    return reply


async def _answer_turn(ctx: TurnContext, agents: Registry, question) -> tuple[TurnReply, str]:
    """Đang có câu hỏi chờ trả lời (kiểm tra từng phần hoặc trắc nghiệm): Assessment chấm, không hỏi Orchestrator."""
    position, prompt, choices = question[1], question[2], question[3]
    graded = await final(agents.get("assessment"), replace(ctx, mode="quiz"))
    if graded.handoff is not None and graded.handoff.target == "orchestrator":
        # Học sinh hỏi điều khác: trả lời bình thường rồi nhắc lại câu hỏi đang chờ
        reply, agent = await _chat_turn(ctx, agents)
        answer = f"{drop_trailing_question(reply.answer)} Quay lại câu hỏi lúc nãy nhé: {prompt}"
        trace = [TraceStep("assessment", "học sinh hỏi điều khác")] + reply.trace
        return replace(reply, answer=answer, sentences=split_sentences(answer), trace=trace), agent
    if choices is None:  # câu hỏi kiểm tra của một phần
        parts = await lesson_parts(ctx.lesson_id)
        invite = NEXT_PART if await get_part(ctx.session_id) < len(parts) else TO_SUMMARY
        return _reply(f"{graded.speech_text} {invite}", [TraceStep("assessment", "chấm câu hỏi kiểm tra")],
                      mode="teach"), "assessment"
    still = await current_question(ctx.session_id)
    return _reply(graded.speech_text, [TraceStep("assessment", f"chấm câu {position}")],
                  mode="quiz" if still is not None and still[3] is not None else "chat"), "assessment"


async def _chat_turn(ctx: TurnContext, agents: Registry) -> tuple[TurnReply, str]:
    trace: list[TraceStep] = []
    routed = await final(agents.get("orchestrator"), ctx)
    if routed.refusal or routed.handoff is None:
        trace.append(TraceStep("orchestrator", "từ chối"))
        return _reply(REFUSED, trace), "orchestrator"
    intent, query = routed.handoff.payload["intent"], routed.handoff.payload["query"]
    trace.append(TraceStep("orchestrator", f"ý định: {intent}"))

    if routed.handoff.target == "assessment":
        result = await final(agents.get("assessment"), ctx)
        started = await current_question(ctx.session_id) is not None
        trace.append(TraceStep("assessment", "tạo bài kiểm tra" if started else "chưa tạo được bài kiểm tra"))
        return _reply(result.speech_text, trace, mode="quiz" if started else "chat"), "assessment"

    if intent == "next" and ctx.lesson_id is not None:
        return await next_part(ctx, agents, trace), "tutor"

    found = await final(agents.get("knowledge"), replace(ctx, text=query))
    evidence: tuple[Evidence, ...] = tuple(found.handoff.payload["evidence"])
    trace.append(TraceStep("knowledge", found.handoff.reason))

    figure = None
    if found.handoff.target == "vision" or (intent == "figure" and any(e.kind == "figure" for e in evidence)):
        seen = await final(agents.get("vision"), replace(ctx, evidence=evidence))
        evidence = tuple(seen.handoff.payload["evidence"])
        figure = seen.handoff.payload.get("figure")
        trace.append(TraceStep("vision", seen.handoff.reason))

    taught = await final(agents.get("tutor"), replace(ctx, evidence=evidence))
    trace.append(TraceStep("tutor", "trả lời gợi mở" if taught.citations else "không tìm thấy trong SGK"))
    answer = _with_disclaimer(taught.speech_text, figure, taught.citations)
    return _reply(answer, trace, _citations(taught.citations, evidence)), "tutor"
