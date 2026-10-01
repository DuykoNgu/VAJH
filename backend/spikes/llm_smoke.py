"""Smoke test THẬT (tốn tiền): mỗi route gọi 1 lần structured + 1 lần streaming qua provider đang chọn.

    cd backend && .venv/bin/python spikes/llm_smoke.py [route ...]     # đọc LLM_PROVIDER, OPENAI_LLM_MODEL từ .env
"""
import asyncio
import logging
import sys

from pydantic import BaseModel

from app.ai.llm import LLMResult, make_llm
from app.config import get_settings


class Echo(BaseModel):
    language: str
    answer: str


class UsageLog(logging.Handler):
    def emit(self, r):
        print(f"  [{r.route}] model={r.model} effort={r.effort} in={r.input_tokens} out={r.output_tokens} "
              f"latency={r.latency_ms}ms outcome={r.outcome}")


async def main(routes):
    settings = get_settings()
    logging.getLogger("lusia.llm").addHandler(UsageLog())
    logging.getLogger("lusia.llm").setLevel(logging.INFO)
    llm = make_llm(settings)
    print(f"provider: {settings.llm_provider}")
    msg = [{"role": "user", "content": "Trả lời một câu ngắn bằng tiếng Việt: 2 + 2 bằng mấy?"}]
    for route in routes or list(settings.llm_routes):
        print(f"route {route}")
        result = await llm.complete(route, msg, schema=Echo)
        print("  structured:", getattr(result, "parsed", result))
        async for event in llm.stream(route, msg):
            if isinstance(event, LLMResult):
                print("  streamed:", event.text.strip()[:80])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
