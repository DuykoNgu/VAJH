"""Spike S4 (độ trễ, gọi API THẬT - tốn tiền): đo các chặng LLM trên đường đi của một lượt hỏi bằng giọng nói.

    cd backend && .venv/bin/python spikes/latency.py [số_lần=10]

- orchestrator: structured output (quyết định route) - thời gian tới khi có kết quả
- tutor: streaming - thời gian tới đoạn text đầu tiên và tới hết CÂU đầu tiên (TTS đọc theo câu)
TTS (ZeroTTS) đo riêng ở spikes/tts_probe.py; STT chờ spike S2.
"""
import asyncio
import re
import statistics
import sys
import time
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy được bằng `python spikes/<file>.py`

from app.config import get_settings
from app.core.ai.llm import LLMResult, Refusal, make_llm

ROUTER_SYSTEM = (
    "Bạn là bộ điều phối của LUSIA, gia sư AI cho học sinh khiếm thị. Đọc câu hỏi và chọn ý định cùng các agent "
    "cần gọi trong số: tutor, knowledge, vision, document, assessment, student_model."
)
TUTOR_SYSTEM = (
    "Bạn là LUSIA, gia sư kiên nhẫn cho học sinh khiếm thị lớp 8. Trả lời bằng tiếng Việt để ĐỌC THÀNH TIẾNG: "
    "câu ngắn, không dùng ký hiệu toán (viết 'y bằng hai x cộng một'), gợi mở bằng một câu hỏi."
)
QUESTION = [{"role": "user", "content": "LUSIA ơi, giải thích giúp mình đồ thị hàm số y = 2x + 1 trong sách Toán 8."}]
SENTENCE_END = re.compile(r"[.!?…](\s|$)")


class Routing(BaseModel):
    intent: str
    target_agents: list[str]


def stats(name: str, values_ms: list[float]) -> str:
    values = sorted(values_ms)
    p90 = values[max(0, round(0.9 * len(values)) - 1)]
    return f"{name:28} p50={statistics.median(values):6.0f} ms  p90={p90:6.0f} ms  max={values[-1]:6.0f} ms"


async def router_once(llm) -> float:
    start = time.perf_counter()
    result = await llm.complete("orchestrator", QUESTION, system=ROUTER_SYSTEM, schema=Routing)
    if not isinstance(result, LLMResult):
        raise RuntimeError(f"orchestrator returned {result!r}")
    return (time.perf_counter() - start) * 1000


async def tutor_once(llm) -> tuple[float, float, float]:
    start = time.perf_counter()
    first_token = first_sentence = None
    text = ""
    async for event in llm.stream("tutor", QUESTION, system=TUTOR_SYSTEM):
        if isinstance(event, Refusal):
            raise RuntimeError(f"tutor refused: {event}")
        if isinstance(event, str):
            now = (time.perf_counter() - start) * 1000
            first_token = first_token or now
            text += event
            if first_sentence is None and SENTENCE_END.search(text):
                first_sentence = now
    total = (time.perf_counter() - start) * 1000
    return first_token, first_sentence or total, total


async def main(runs: int) -> None:
    settings = get_settings()
    llm = make_llm(settings)
    route = settings.llm_routes
    print(f"provider={settings.llm_provider} orchestrator={route['orchestrator'].model}/{route['orchestrator'].effort} "
          f"tutor={route['tutor'].model}/{route['tutor'].effort} runs={runs}")
    await router_once(llm)  # làm nóng kết nối, không tính
    router = [await router_once(llm) for _ in range(runs)]
    tutor = [await tutor_once(llm) for _ in range(runs)]
    print(stats("orchestrator (structured)", router))
    print(stats("tutor first token", [t[0] for t in tutor]))
    print(stats("tutor first sentence", [t[1] for t in tutor]))
    print(stats("tutor full answer", [t[2] for t in tutor]))
    llm_to_first_sentence = statistics.median(router) + statistics.median(t[1] for t in tutor)
    print(f"orchestrator p50 + tutor first sentence p50 = {llm_to_first_sentence:.0f} ms "
          f"(+ STT, + TTS first chunk ~85 ms from S3)")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 10))
