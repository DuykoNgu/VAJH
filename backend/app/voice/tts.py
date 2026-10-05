"""Text-to-Speech tiếng Việt bằng ZeroTTS (chạy CPU, trong tiến trình API).

stream(): phát dần - model sinh từng khúc 80 ms (khúc đầu ~0,1 s) → mã hoá MP3 → gửi ngay, không chờ hết câu.
synthesize(): cả câu thành WAV (POST /tts, làm nóng lúc khởi động).

Tải model một lần:  python -m app.voice.tts --download
(tải về thư mục thường: onnxruntime mới từ chối file model qua symlink của cache Hugging Face)
"""
import asyncio
import io
import sys
import threading
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import closing

from app.ai.speech import Speech, SynthesizeRequest
from app.config import Settings, get_settings

FILLER = "Để mình xem sách nhé."  # chỉ dùng để làm nóng model lúc khởi động (trang học không còn đọc câu chờ)
CACHE_SIZE = 256  # câu lặp lại (nhắc lại, lựa chọn quiz, menu) không phải tổng hợp lại


def _remember(cache: OrderedDict, key: str, value: bytes) -> None:
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > CACHE_SIZE:
        cache.popitem(last=False)


class ZeroTTSEngine:
    stream_format = "audio/mpeg"

    def __init__(self, settings: Settings):
        self.model_dir = settings.zerotts_model_dir
        self.voice = settings.zerotts_voice
        self._model = None
        # Model không dùng song song được: mỗi lúc một câu. Khóa ở mức luồng (không phải asyncio) để luồng của một
        # stream đã bị huỷ vẫn giữ model tới khi nó thật sự dừng.
        # ponytail: một model cho cả tiến trình; tách TTS ra tiến trình/máy riêng nếu nhiều học sinh phải xếp hàng
        self._lock = threading.Lock()
        self._wav: OrderedDict[str, bytes] = OrderedDict()
        self._mp3: OrderedDict[str, bytes] = OrderedDict()

    def _load(self):  # gọi khi đang giữ self._lock
        if self._model is None:
            from zerotts import ZeroTTS

            if not (self.model_dir / "config.json").exists():
                raise RuntimeError(f"ZeroTTS model not found in {self.model_dir}: run `python -m app.voice.tts --download`")
            self._model = ZeroTTS.from_pretrained(str(self.model_dir))
        return self._model

    def _render(self, text: str) -> bytes:
        import numpy as np
        import soundfile as sf

        with self._lock:
            model = self._load()
            audio = np.asarray(model.synthesize(text, voice=self.voice)).squeeze()
        buffer = io.BytesIO()
        sf.write(buffer, audio, model.sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()

    async def synthesize(self, request: SynthesizeRequest) -> Speech:
        text = request.text
        if text not in self._wav:  # câu đã có không phải chờ câu khác đang tổng hợp
            _remember(self._wav, text, await asyncio.to_thread(self._render, text))
        self._wav.move_to_end(text)
        return Speech(self._wav[text], "audio/wav")

    def _stream_mp3(self, text: str, emit: Callable[[bytes], None], cancelled: threading.Event) -> bytes | None:
        """Chạy trong luồng riêng: sinh từng khúc, mã hoá MP3, emit() ngay. None nếu bị huỷ giữa chừng."""
        import numpy as np

        from app.voice.mp3 import Mp3Encoder

        parts: list[bytes] = []
        with self._lock:
            model = self._load()
            encoder = Mp3Encoder(model.sample_rate)
            try:
                with closing(model.synthesize_stream(text, voice=self.voice)) as chunks:
                    for chunk in chunks:
                        if cancelled.is_set():  # học sinh ngắt lời: trả model cho câu trả lời mới
                            return None
                        if piece := encoder.feed(np.asarray(chunk, dtype=np.float32)):
                            parts.append(piece)
                            emit(piece)
                if piece := encoder.close():
                    parts.append(piece)
                    emit(piece)
            finally:
                encoder.close()
        return b"".join(parts)

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """Audio MP3 của một câu, gửi dần khi model đang sinh; câu đã có trong cache thì gửi ngay."""
        if (cached := self._mp3.get(text)) is not None:
            self._mp3.move_to_end(text)
            yield cached
            return
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        cancelled = threading.Event()
        work = loop.run_in_executor(None, self._stream_mp3, text,
                                    lambda piece: loop.call_soon_threadsafe(queue.put_nowait, piece), cancelled)

        def finished(future: asyncio.Future) -> None:
            if not future.cancelled():
                future.exception()  # lỗi được ném ra ở `await work` bên dưới (hoặc bỏ qua nếu stream đã bị huỷ)
            queue.put_nowait(None)

        work.add_done_callback(finished)  # chạy sau mọi emit() của luồng (cùng hàng đợi của event loop)
        try:
            while (piece := await queue.get()) is not None:
                yield piece
            if full := await work:
                _remember(self._mp3, text, full)
        finally:
            cancelled.set()  # trình duyệt ngắt kết nối / dừng đọc: luồng tổng hợp dừng ở khúc kế tiếp

    async def warm_up(self) -> None:
        """Nạp model và tổng hợp sẵn một câu lúc khởi động (chạy nền) để câu đầu tiên không phải chờ."""
        try:
            await self.synthesize(SynthesizeRequest(text=FILLER, language="vi"))
            async for _ in self.stream(FILLER):  # khởi tạo nhánh phát dần (bộ giải mã streaming, bộ mã hoá MP3)
                pass
        except Exception as e:  # thiếu model: API vẫn chạy, /tts báo lỗi rõ ràng khi được gọi
            print(f"ZeroTTS warm-up skipped: {e}", file=sys.stderr)


def download(settings: Settings) -> None:
    from huggingface_hub import snapshot_download

    path = snapshot_download("zeroweight-ai/ZeroTTS", local_dir=str(settings.zerotts_model_dir))
    print(f"ZeroTTS model ready in {path}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--download"]:
        sys.exit("usage: python -m app.voice.tts --download")
    download(get_settings())
