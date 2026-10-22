"""E2E LUSIA qua HTTP thật (API + worker đang chạy), in và ghi số liệu.

    cd backend && .venv/bin/python e2e/run.py --api http://localhost:8010 --pdf <sgk.pdf> --out report.json

Kịch bản: health → giáo viên tải SGK → worker nạp → duyệt hình, xuất bản → học sinh học từng bài (giảng, trả lời câu
kiểm tra, học tiếp, hỏi tự do, hỏi ngoài SGK, hỏi về hình, làm quiz) → đọc TTS → đánh giá retrieval → số liệu /monitor.
Script đọc cùng biến môi trường với API (DATABASE_URL, EMBEDDING_PROVIDER, ...) để đánh giá retrieval trực tiếp trên DB.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from uuid import UUID

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy được bằng `python e2e/run.py`

from app.config import get_settings  # noqa: E402
from app.core.rag.embeddings import make_embeddings  # noqa: E402
from app.core.rag.retrieval import search_knowledge  # noqa: E402
from app.core.storage import relational  # noqa: E402
from app.features.learning.agents.tutor import NOT_FOUND, REFUSED  # noqa: E402

TEACHER = {"X-Dev-User": "colan"}
STUDENT = {"X-Dev-User": "minh5a"}
INGEST_TIMEOUT_S = 3600
OFF_TOPIC = "Hôm nay trời có mưa không?"
FIGURE_QUESTION = "Hình vẽ trong bài này cho biết điều gì?"
QUIZ_ANSWERS = ["A", "B", "A"]


def ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


class Run:
    def __init__(self, api: httpx.AsyncClient):
        self.api = api
        self.errors: list[dict] = []
        self.turns: list[dict] = []

    async def call(self, method: str, url: str, headers: dict, **kwargs) -> tuple[httpx.Response, int]:
        started = time.perf_counter()
        r = await self.api.request(method, url, headers=headers, **kwargs)
        took = ms(started)
        if r.status_code >= 400:
            self.errors.append({"call": f"{method} {url}", "status": r.status_code, "body": r.text[:300]})
        return r, took

    async def turn(self, label: str, lesson: str, url: str, body: dict) -> dict:
        r, took = await self.call("POST", url, STUDENT, json=body)
        reply = r.json() if r.status_code < 400 else {}
        answer = reply.get("answer", "")
        row = {"label": label, "lesson": lesson, "ms": took, "status": r.status_code, "mode": reply.get("mode"),
               "agents": [s["agent"] for s in reply.get("trace", [])], "citations": len(reply.get("citations", [])),
               "sentences": len(reply.get("sentences", [])), "chars": len(answer),
               "not_found": NOT_FOUND in answer, "refused": REFUSED in answer,
               "trace_id": reply.get("trace_id"), "answer": answer[:200]}
        self.turns.append(row)
        print(f"  {label:<14} {took:>6} ms  mode={row['mode']}  cite={row['citations']}  {answer[:90]!r}")
        return reply


async def ingest(run: Run, pdf: Path) -> dict:
    files = {"file": (pdf.name, pdf.read_bytes(), "application/pdf")}
    data = {"title": "Toán 8 (E2E)", "subject": "toan", "grade": "8"}
    r, upload_ms = await run.call("POST", "/curation/documents", TEACHER, files=files, data=data)
    r.raise_for_status()
    doc_id = r.json()["id"]
    started, progress, last = time.perf_counter(), [], None
    while time.perf_counter() - started < INGEST_TIMEOUT_S:
        doc = (await run.call("GET", f"/curation/documents/{doc_id}", TEACHER))[0].json()["document"]
        step = (doc["progress"] or doc["status"]).split(" ")[0:3]
        if step != last:
            progress.append({"at_s": round(time.perf_counter() - started, 1), "step": doc["progress"] or doc["status"]})
            last = step
        if doc["status"] != "processing":
            break
        await asyncio.sleep(2)
    took = round(time.perf_counter() - started, 1)
    # status "ready" có trước bước rút dàn ý; trace ingest chỉ ghi khi cả pipeline (kể cả dàn ý) xong
    while doc["status"] == "ready" and time.perf_counter() - started < INGEST_TIMEOUT_S:
        if (await run.call("GET", "/monitor/traces", TEACHER, params={"kind": "ingest", "limit": 1}))[0].json():
            break
        await asyncio.sleep(2)
    outline_s = round(time.perf_counter() - started, 1)
    print(f"ingest {doc['status']} in {took} s (dàn ý xong ở {outline_s} s): {doc['page_count']} trang, {doc['lessons']} bài, "
          f"{doc['text_chunks']} đoạn, {doc['figures']} hình")
    return {"document_id": doc_id, "upload_ms": upload_ms, "ingest_s": took, "outline_done_s": outline_s, "status": doc["status"],
            "error": doc["error"], "pages": doc["page_count"], "lessons": doc["lessons"],
            "text_chunks": doc["text_chunks"], "figures": doc["figures"], "pending_figures": doc["pending_figures"],
            "seconds_per_page": round(took / doc["page_count"], 2) if doc["page_count"] else None,
            "progress": progress}


async def curate(run: Run, doc_id: str) -> tuple[dict, list[dict]]:
    detail, detail_ms = await run.call("GET", f"/curation/documents/{doc_id}", TEACHER)
    lessons = detail.json()["lessons"]
    approved, approve_ms = await run.call("POST", f"/curation/documents/{doc_id}/figures/approve-all", TEACHER)
    published, publish_ms = await run.call("POST", f"/curation/documents/{doc_id}/publish", TEACHER)
    visible = any(d["id"] == doc_id for d in (await run.call("GET", "/documents", STUDENT))[0].json())
    points = [len([p for p in lesson["outline"] if p["position"] > 0]) for lesson in lessons]
    return {"detail_ms": detail_ms, "approve_ms": approve_ms, "publish_ms": publish_ms,
            "approved": approved.json() if approved.status_code < 400 else None,
            "published": published.status_code < 400 and published.json()["published"],
            "student_sees_document": visible, "lessons_with_outline": sum(n > 0 for n in points),
            "outline_points": sum(points)}, lessons


async def learn(run: Run, lesson: dict) -> None:
    title = lesson["title"]
    print(f"bài: {title}")
    started = await run.turn("vào bài", title, "/sessions", {"lesson_id": lesson["id"]})
    if "id" not in started:
        return
    turns = f"/sessions/{started['id']}/turns"
    points = [p for p in lesson["outline"] if p["position"] > 0 and p["answer"]]
    await run.turn("trả lời đúng", title, turns, {"text": points[0]["answer"] if points else "Em chưa biết ạ"})
    await run.turn("học tiếp", title, turns, {"text": "tiếp"})
    await run.turn("trả lời sai", title, turns, {"text": "Em không biết"})
    question = points[-1]["question"] if points else f"{title} là gì?"
    await run.turn("hỏi tự do", title, turns, {"text": question})
    await run.turn("ngoài SGK", title, turns, {"text": OFF_TOPIC})
    if any(p["kind"] == "figure" for p in lesson["parts"]):
        await run.turn("hỏi hình", title, turns, {"text": FIGURE_QUESTION})
    reply = await run.turn("kiểm tra", title, turns, {"text": "Kiểm tra mình đi"})
    for answer in QUIZ_ANSWERS:
        if reply.get("mode") != "quiz":
            break
        reply = await run.turn("trả lời quiz", title, turns, {"text": answer})
    await run.call("POST", f"/sessions/{started['id']}/end", STUDENT)


async def speech(run: Run) -> dict:
    sentences = next((t["answer"] for t in run.turns if t["label"] == "vào bài" and t["answer"]), "Xin chào em.")
    sentences = [s.strip() + "." for s in sentences.split(".") if s.strip()][:3]
    started = time.perf_counter()
    first, size = None, 0
    async with run.api.stream("POST", "/tts/stream", json={"sentences": sentences}) as r:
        async for chunk in r.aiter_bytes():
            first = first or ms(started)
            size += len(chunk)
    stream_ms = ms(started)
    single, single_ms = await run.call("POST", "/tts", {}, json={"text": sentences[0]})
    return {"stream_sentences": len(sentences), "stream_first_byte_ms": first, "stream_total_ms": stream_ms,
            "stream_bytes": size, "single_ms": single_ms, "single_bytes": len(single.content)}


async def retrieval(doc_id: str) -> dict:
    """Câu hỏi trong dàn ý → các đoạn nguồn của ý đó phải nằm trong top-k (trong bài, như khi học thật)."""
    settings = get_settings()
    k = settings.rag_top_k
    embeddings = make_embeddings(settings)
    await relational.open_pool(settings.database_url)
    try:
        async with relational.connection() as conn:
            golden = await (await conn.execute(
                "SELECT p.lesson_id, p.question, p.chunk_ids FROM lesson_points p JOIN lessons l ON l.id = p.lesson_id"
                " WHERE l.document_id = %s AND p.question IS NOT NULL AND cardinality(p.chunk_ids) > 0",
                (UUID(doc_id),))).fetchall()
            texts = await (await conn.execute(
                "SELECT id, lesson_id, left(content, 160) FROM chunks WHERE document_id = %s AND kind = 'text'"
                " AND lesson_id IS NOT NULL ORDER BY random() LIMIT 40", (UUID(doc_id),))).fetchall()

        async def rank(query: str, lesson_id, expected: set[int], scope_lesson: bool) -> tuple[int | None, int]:
            started = time.perf_counter()
            found = await search_knowledge(embeddings, query, lesson_id if scope_lesson else None, k)
            ids = [e.chunk_id for e in found]
            return next((i for i, c in enumerate(ids) if c in expected), None), ms(started)

        def score(ranks: list[int | None]) -> dict:
            n = len(ranks)
            return {"queries": n, **({} if not n else {
                "hit@1": round(sum(r == 0 for r in ranks) / n, 3),
                "hit@3": round(sum(r is not None and r < 3 for r in ranks) / n, 3),
                f"hit@{k}": round(sum(r is not None for r in ranks) / n, 3),
                "mrr": round(sum(1 / (r + 1) for r in ranks if r is not None) / n, 3)})}

        out, latencies = {"k": k}, []
        for name, rows, scope in [("outline_in_lesson", golden, True), ("outline_whole_document", golden, False)]:
            ranks = []
            for lesson_id, question, chunk_ids in rows:
                r, took = await rank(question, lesson_id, set(chunk_ids), scope)
                ranks.append(r)
                latencies.append(took)
            out[name] = score(ranks)
        ranks = []
        for chunk_id, lesson_id, head in texts:  # mức sàn: tìm lại chính đoạn từ 160 ký tự đầu của nó
            r, took = await rank(head, lesson_id, {chunk_id}, True)
            ranks.append(r)
            latencies.append(took)
        out["self_retrieval_in_lesson"] = score(ranks)
        out["search_p50_ms"], out["search_p95_ms"] = pct(latencies, 0.5), pct(latencies, 0.95)
        return out
    finally:
        await relational.close_pool()


async def monitor(run: Run) -> dict:
    summary = (await run.call("GET", "/monitor/summary", TEACHER, params={"hours": 24}))[0].json()
    tokens = []
    for t in run.turns:
        if t["trace_id"]:
            spans = (await run.call("GET", f"/monitor/traces/{t['trace_id']}", TEACHER))[0].json()["spans"]
            llm = [s for s in spans if s["kind"] == "llm"]
            t["llm_calls"] = len(llm)
            t["tokens_in"] = sum(s["input_tokens"] or 0 for s in llm)
            t["tokens_out"] = sum(s["output_tokens"] or 0 for s in llm)
            tokens.append(t)
    ingest = (await run.call("GET", "/monitor/traces", TEACHER, params={"kind": "ingest", "limit": 1}))[0].json()
    return {"summary": summary, "ingest_trace": ingest[0] if ingest else None}


def turn_stats(turns: list[dict]) -> dict:
    by_label: dict[str, list[int]] = {}
    for t in turns:
        by_label.setdefault(t["label"], []).append(t["ms"])
    answered = [t for t in turns if t["label"] in ("hỏi tự do", "hỏi hình")]
    latency = [t["ms"] for t in turns]
    return {
        "turns": len(turns), "http_errors": sum(t["status"] >= 400 for t in turns),
        "p50_ms": pct(latency, 0.5), "p95_ms": pct(latency, 0.95), "max_ms": max(latency, default=None),
        "by_step": {k: {"n": len(v), "p50_ms": pct(v, 0.5), "max_ms": max(v)} for k, v in by_label.items()},
        "grounded_answer_rate": round(sum(t["citations"] > 0 for t in answered) / len(answered), 3) if answered else None,
        "off_topic_declined": [t["not_found"] or t["refused"] for t in turns if t["label"] == "ngoài SGK"],
        "quiz_started": [t["mode"] == "quiz" for t in turns if t["label"] == "kiểm tra"],
        "avg_sentences": round(statistics.mean(t["sentences"] for t in turns), 1) if turns else None,
        "tokens_in_per_turn": pct([t.get("tokens_in", 0) for t in turns], 0.5),
        "tokens_out_per_turn": pct([t.get("tokens_out", 0) for t in turns], 0.5),
        "llm_calls_per_turn": pct([t.get("llm_calls", 0) for t in turns], 0.5),
    }


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="E2E LUSIA và số liệu")
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--document", help="dùng lại tài liệu đã nạp + xuất bản (bỏ qua tải lên / nạp)")
    parser.add_argument("--lessons", type=int, default=2, help="số bài học sinh học thử")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    async with httpx.AsyncClient(base_url=args.api, timeout=600) as api:
        run = Run(api)
        health, health_ms = await run.call("GET", "/health/ready", {})
        report = {"provider": get_settings().llm_provider, "health": {"status": health.status_code, "ms": health_ms}}
        if args.document:
            report["ingest"] = {"document_id": args.document, "status": "ready", "reused": True}
        else:
            report["ingest"] = await ingest(run, args.pdf)
        if report["ingest"]["status"] == "ready":
            report["curation"], lessons = await curate(run, report["ingest"]["document_id"])
            for lesson in [x for x in lessons if len(x["teaching"]) >= 2][:args.lessons]:
                await learn(run, lesson)
            report["tts"] = await speech(run)
            report["retrieval"] = await retrieval(report["ingest"]["document_id"])
            report["monitor"] = await monitor(run)
        report["learning"] = turn_stats(run.turns)
        report["turns"] = run.turns
        report["http_errors"] = run.errors
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report → {args.out}  ({len(run.errors)} lỗi HTTP)")
    return 1 if run.errors or report["ingest"]["status"] != "ready" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
