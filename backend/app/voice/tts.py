"""Text-to-Speech tiếng Việt bằng ZeroTTS (chạy CPU, trong tiến trình API).

Tải model một lần:  python -m app.voice.tts --download
(tải về thư mục thường: onnxruntime mới từ chối file model qua symlink của cache Hugging Face)
"""
import asyncio
import io
import sys
from collections import OrderedDict

from app.ai.speech import Speech, SynthesizeRequest
from app.config import Settings, get_settings

FILLER = "Để mình xem sách nhé."  # phát ngay khi học sinh vừa hỏi, che thời gian các agent xử lý
CACHE_SIZE = 256  # câu lặp lại (lựa chọn quiz, câu đệm) không phải tổng hợp lại


class ZeroTTSEngine:
    def __init__(self, settings: Settings):
        self.model_dir = settings.zerotts_model_dir
        self.voice = settings.zerotts_voice
        self._model = None
        self._lock = asyncio.Lock()  # ponytail: một khóa cho cả tiến trình; tách TTS ra tiến trình riêng nếu phải xếp hàng
        self._cache: OrderedDict[str, bytes] = OrderedDict()

    def _render(self, text: str) -> bytes:
        import numpy as np
        import soundfile as sf

        if self._model is None:
            from zerotts import ZeroTTS

            if not (self.model_dir / "config.json").exists():
                raise RuntimeError(f"ZeroTTS model not found in {self.model_dir}: run `python -m app.voice.tts --download`")
            self._model = ZeroTTS.from_pretrained(str(self.model_dir))
        audio = np.asarray(self._model.synthesize(text, voice=self.voice)).squeeze()
        buffer = io.BytesIO()
        sf.write(buffer, audio, self._model.sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()

    async def synthesize(self, request: SynthesizeRequest) -> Speech:
        text = request.text
        async with self._lock:
            if text not in self._cache:
                self._cache[text] = await asyncio.to_thread(self._render, text)
                if len(self._cache) > CACHE_SIZE:
                    self._cache.popitem(last=False)
            self._cache.move_to_end(text)
            return Speech(self._cache[text], "audio/wav")


    async def warm_up(self) -> None:
        """Nạp model và tổng hợp sẵn câu đệm lúc khởi động (chạy nền) để câu đầu tiên không phải chờ."""
        try:
            await self.synthesize(SynthesizeRequest(text=FILLER, language="vi"))
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
