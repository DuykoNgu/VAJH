"""ZeroTTSEngine với model giả: phát dần đúng, cache, huỷ khi ngắt lời, câu có sẵn không chờ khóa."""
import asyncio
import io
import time

import numpy as np
import soundfile as sf

from app.config import get_settings
from app.voice.tts import ZeroTTSEngine

SR = 48000
CHUNK = 3840  # 80 ms


class SlowModel:
    """Sinh `chunks` khúc 80 ms, mỗi khúc mất `delay` giây (như model thật nhưng nhanh hơn)."""

    sample_rate = SR

    def __init__(self, chunks=10, delay=0.02):
        self.chunks, self.delay, self.calls, self.produced = chunks, delay, 0, 0

    def synthesize_stream(self, text, voice=None):
        self.calls += 1
        for i in range(self.chunks):
            time.sleep(self.delay)
            self.produced += 1
            yield (0.3 * np.sin(2 * np.pi * 220 * (np.arange(CHUNK) + i * CHUNK) / SR)).astype(np.float32)[None, :]

    def synthesize(self, text, voice=None):
        return np.concatenate([c for c in self.synthesize_stream(text, voice)], axis=1)


def engine(model) -> ZeroTTSEngine:
    e = ZeroTTSEngine(get_settings())
    e._model = model
    return e


async def collect(e, text):
    return b"".join([piece async for piece in e.stream(text)])


async def test_stream_is_playable_and_cached():
    model = SlowModel()
    e = engine(model)
    data = await collect(e, "Phần 1.")
    assert 0.8 <= len(sf.read(io.BytesIO(data))[0]) / SR <= 0.95       # 10 khúc × 80 ms
    assert await collect(e, "Phần 1.") == data and model.calls == 1      # lần hai lấy từ cache


async def test_first_audio_arrives_before_the_sentence_is_finished():
    model = SlowModel(chunks=20, delay=0.03)
    e = engine(model)
    agen = e.stream("Một câu dài.")
    await agen.__anext__()
    assert model.produced < model.chunks                                 # còn đang sinh mà đã có audio gửi đi
    await agen.aclose()


async def test_interrupt_stops_synthesis_and_frees_the_model():
    model = SlowModel(chunks=50, delay=0.02)
    e = engine(model)
    agen = e.stream("Câu sẽ bị ngắt.")
    await agen.__anext__()
    await agen.aclose()                                                  # học sinh ngắt lời
    assert await asyncio.to_thread(e._lock.acquire, True, 2)             # luồng tổng hợp dừng và trả model
    e._lock.release()
    assert model.produced < model.chunks and "Câu sẽ bị ngắt." not in e._mp3
    assert await collect(e, "Câu mới.")                                  # câu trả lời mới không phải chờ


async def test_cached_sentence_does_not_wait_for_a_running_synthesis():
    model = SlowModel(chunks=5, delay=0.01)
    e = engine(model)
    cached = await collect(e, "Mình bắt đầu bài nhé.")
    model.delay = 0.5                                                    # một câu khác đang tổng hợp rất chậm
    slow = asyncio.create_task(collect(e, "Câu chậm."))
    await asyncio.sleep(0.05)
    started = time.perf_counter()
    assert await collect(e, "Mình bắt đầu bài nhé.") == cached
    assert time.perf_counter() - started < 0.1
    slow.cancel()
