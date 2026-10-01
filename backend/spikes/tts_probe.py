"""Spike S3 (TTS): đo ZeroTTS trên CPU - thời gian tới đoạn audio đầu, RTF, và xuất WAV để nghe.

    ZEROTTS_MODEL=/path/to/local/model python spikes/tts_probe.py OUT_DIR [voice]
Chạy trong venv riêng có `pip install zerotts` (model ~900 MB; không thêm vào requirements backend).
onnxruntime >= 1.2x từ chối file model qua symlink của HF cache → tải model về thư mục thường:
    huggingface_hub.snapshot_download("zeroweight-ai/ZeroTTS", local_dir=...)
"""
import os
import statistics
import sys
import time
from pathlib import Path

import soundfile as sf
from zerotts import ZeroTTS

SENTENCES = [
    "Chào em, hôm nay mình cùng học bài Hàm số bậc nhất nhé.",
    "Đồ thị của hàm số y bằng hai x cộng một là một đường thẳng.",
    "Đường thẳng này đi lên từ trái sang phải và cắt trục tung tại điểm có tung độ bằng một.",
    "Em thử thay x bằng không vào công thức xem y bằng bao nhiêu nhé?",
    "Đúng rồi! Khi x bằng không thì y bằng một.",
    "Hệ số góc a bằng hai, nên khi x tăng một đơn vị thì y tăng hai đơn vị.",
    "Phân số ba phần tư bằng không phẩy bảy lăm.",
    "Công thức hóa học của nước là H hai O.",
    "Câu hỏi số một: đồ thị cắt trục tung tại điểm nào? A, không. B, một. C, hai.",
    "Em làm tốt lắm, mình chuyển sang câu tiếp theo nhé.",
]


def main(out_dir: str, voice: str | None = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    tts = ZeroTTS.from_pretrained(os.environ.get("ZEROTTS_MODEL", "zeroweight-ai/ZeroTTS"))
    tts.warmup()
    print(f"load+warmup: {time.perf_counter() - t0:.1f}s  voices: {tts.list_voices()}")
    first, rtf = [], []
    for i, text in enumerate(SENTENCES, 1):
        start = time.perf_counter()
        chunks, t_first = [], None
        for chunk in tts.synthesize_stream(text, voice=voice):
            t_first = t_first or time.perf_counter() - start
            chunks.append(chunk)
        elapsed = time.perf_counter() - start
        path = str(out / f"{i:02d}.wav")
        tts.save_audio(tts.synthesize(text, voice=voice), path)
        seconds = sf.info(path).duration
        first.append(t_first * 1000)
        rtf.append(elapsed / seconds)
        print(f"{i:02d} first_chunk={t_first * 1000:5.0f}ms stream_total={elapsed:5.2f}s audio={seconds:5.2f}s "
              f"rtf={elapsed / seconds:.2f}")
    print(f"first chunk p50={statistics.median(first):.0f}ms max={max(first):.0f}ms; "
          f"rtf p50={statistics.median(rtf):.2f} max={max(rtf):.2f}; WAVs in {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
