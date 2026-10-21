"""Trace agent + LLM và trang giám sát."""
import base64

import pytest

from app.core import tracing
from app.core.ai.llm import Refusal, image_block
from tests.conftest import as_user, running_app
from tests.features.learning.test_learning import ANSWER, EXPLAIN_ROUTE, ask, session

TEACHER = as_user("colan")


@pytest.fixture
async def api(test_database):
    async with running_app() as client:
        yield client


@pytest.fixture
def people(make_student, make_teacher):
    make_student("minh8a")
    make_teacher("colan")


async def test_turn_trace_nests_llm_calls_under_agents(api, people, textbook, db):
    sid = await session(api, textbook["lessons"][1], db)
    reply = await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE, {"answer": ANSWER, "cited": [1]})
    detail = (await api.get(f"/monitor/traces/{reply['trace_id']}", headers=TEACHER)).json()
    assert detail["kind"] == "turn" and detail["status"] == "ok" and detail["input"] == "Hàm số bậc nhất là gì?"
    assert detail["output"] == reply["answer"]
    spans = detail["spans"]
    agents = {s["seq"]: s["name"] for s in spans if s["kind"] == "agent"}
    assert list(agents.values()) == ["orchestrator", "knowledge", "tutor"]
    llm = [(agents[s["parent_seq"]], s["name"]) for s in spans if s["kind"] == "llm"]
    assert llm == [("orchestrator", "orchestrator"), ("tutor", "tutor")]          # LLM nằm dưới agent gọi nó
    tutor_call = next(s for s in spans if s["kind"] == "llm" and s["name"] == "tutor")
    assert tutor_call["detail"]["system"] and ANSWER in tutor_call["detail"]["response"]
    assert "Hàm số bậc nhất là gì?" in tutor_call["detail"]["messages"][-1]["content"]
    knowledge = next(s for s in spans if s["name"] == "knowledge")
    assert knowledge["detail"]["handoff"]["target"] == "tutor"


async def test_errors_are_traced(api, people, textbook, db):
    sid = await session(api, textbook["lessons"][1], db)
    api.app.state.llm.script(RuntimeError("provider down"))
    with pytest.raises(RuntimeError):
        await api.post(f"/sessions/{sid}/turns", json={"text": "Hàm số là gì?"}, headers=as_user("minh8a"))
    status, error = db.execute("SELECT status, error FROM traces WHERE kind = 'turn'").fetchone()
    assert status == "error" and "provider down" in error
    span = db.execute("SELECT s.name, s.status, s.detail->>'error' FROM trace_spans s JOIN traces t ON t.id = s.trace_id"
                      " WHERE t.kind = 'turn' AND s.kind = 'llm'").fetchone()
    assert span[:2] == ("orchestrator", "error") and "provider down" in span[2]


async def test_images_are_not_stored(api, db):
    llm = api.app.state.llm
    llm.script("ok")
    png = b"\x89PNG" + b"0" * 120 * 1024
    async with tracing.trace("ingest") as t:
        await llm.complete("vision_offline", [{"role": "user", "content": [image_block(png, "image/png"),
                                                                            {"type": "text", "text": "Mô tả"}]}])
    stored = db.execute("SELECT detail->'messages'->0->>'content' FROM trace_spans WHERE trace_id = %s",
                        (t.id,)).fetchone()[0]
    assert stored.startswith("[ảnh PNG 120 KB]") and base64.b64encode(png)[:40].decode() not in stored


async def test_summary_and_rating(api, people, textbook, db):
    sid = await session(api, textbook["lessons"][1], db)
    await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE, {"answer": ANSWER, "cited": [1]})
    second = await ask(api, sid, "Còn gì nữa?", Refusal("other"))                 # Orchestrator từ chối
    summary = (await api.get("/monitor/summary?hours=1", headers=TEACHER)).json()
    kinds = {k["kind"]: k for k in summary["kinds"]}
    assert kinds["turn"]["count"] == 2 and kinds["lesson_start"]["count"] == 1
    routes = {r["route"]: r for r in summary["routes"]}
    assert routes["orchestrator"]["calls"] == 2 and routes["orchestrator"]["refusals"] == 1
    assert {a["agent"] for a in summary["agents"]} >= {"orchestrator", "knowledge", "tutor"}
    assert summary["quality"]["turns"] == 2 and summary["estimated_cost_usd"] is None

    r = await api.post(f"/monitor/traces/{second['trace_id']}/rating", json={"rating": -1, "note": "giảng sai dấu"},
                       headers=TEACHER)
    assert r.json()["rating"] == -1 and r.json()["note"] == "giảng sai dấu"
    assert (await api.get("/monitor/summary?hours=1", headers=TEACHER)).json()["quality"]["thumbs_down"] == 1
    down = (await api.get("/monitor/traces?rated=down", headers=TEACHER)).json()
    assert [t["id"] for t in down] == [second["trace_id"]]


async def test_trace_failure_never_breaks_the_turn(api, people, textbook, db, monkeypatch):
    from types import SimpleNamespace

    def broken():
        raise RuntimeError("db down")

    sid = await session(api, textbook["lessons"][1], db)
    monkeypatch.setattr(tracing, "relational", SimpleNamespace(transaction=broken))  # chỉ phần ghi trace hỏng
    reply = await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE, {"answer": ANSWER, "cited": [1]})
    assert reply["answer"].endswith(ANSWER)


async def test_students_cannot_read_monitoring(api, people):
    assert (await api.get("/monitor/summary", headers=as_user("minh8a"))).status_code == 400


@pytest.fixture
def sampled(monkeypatch):
    from app.config import get_settings

    def set_rate(rate):
        monkeypatch.setattr(get_settings(), "trace_payloads", "sampled")
        monkeypatch.setattr(get_settings(), "trace_sample_rate", rate)
    return set_rate


async def test_unsampled_successful_turn_keeps_metrics_only(api, people, textbook, db, sampled):
    sid = await session(api, textbook["lessons"][1], db)
    sampled(0)
    reply = await ask(api, sid, "Hàm số bậc nhất là gì?", EXPLAIN_ROUTE, {"answer": ANSWER, "cited": [1]})
    spans = (await api.get(f"/monitor/traces/{reply['trace_id']}", headers=TEACHER)).json()["spans"]
    assert all(s["detail"]["payload"] == "omitted" for s in spans)
    assert not any(k in s["detail"] for s in spans for k in ("system", "messages", "response", "input", "output"))
    assert next(s for s in spans if s["name"] == "knowledge")["detail"]["handoff"]["target"] == "tutor"
    assert all(s["duration_ms"] >= 0 for s in spans) and {s["status"] for s in spans} == {"ok"}


async def test_failed_turn_keeps_its_prompts(api, people, textbook, db, sampled):
    sid = await session(api, textbook["lessons"][1], db)
    sampled(0)
    reply = await ask(api, sid, "Còn gì nữa?", Refusal("other"))
    spans = (await api.get(f"/monitor/traces/{reply['trace_id']}", headers=TEACHER)).json()["spans"]
    llm = next(s for s in spans if s["kind"] == "llm")
    assert llm["status"] == "refusal" and llm["detail"]["system"] and "payload" not in llm["detail"]


async def test_old_payloads_purged_rated_trace_kept(api, people, textbook, db):
    sid = await session(api, textbook["lessons"][1], db)
    ids = [(await ask(api, sid, f"Câu {i}", EXPLAIN_ROUTE, {"answer": ANSWER, "cited": [1]}))["trace_id"]
           for i in range(3)]
    unrated, rated, ancient = ids
    db.execute("UPDATE traces SET started_at = now() - interval '10 days' WHERE id IN (%s, %s)", (unrated, rated))
    db.execute("UPDATE traces SET started_at = now() - interval '100 days' WHERE id = %s", (ancient,))
    db.execute("UPDATE traces SET rating = 1 WHERE id = %s", (rated,))
    result = await tracing.purge(7, 90)
    assert result["deleted_traces"] == 1 and result["purged_traces"] == 1
    assert db.execute("SELECT count(*) FROM traces WHERE id = %s", (ancient,)).fetchone()[0] == 0
    first = (await api.get(f"/monitor/traces/{unrated}", headers=TEACHER)).json()
    assert first["input"] is None and all(s["detail"].get("payload") == "purged" for s in first["spans"])
    assert all("system" not in s["detail"] for s in first["spans"]) and first["spans"][0]["duration_ms"] >= 0
    kept = (await api.get(f"/monitor/traces/{rated}", headers=TEACHER)).json()
    assert kept["input"] == "Câu 1" and any("system" in s["detail"] for s in kept["spans"])
