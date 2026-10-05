"""Mã hoá MP3 phát dần cho /tts/stream: mỗi khúc audio vừa sinh ra → byte MP3 gửi ngay cho trình duyệt.

Bộ mã hoá (libsndfile + LAME) ghi một frame Xing/LAME ở đầu rồi GHI ĐÈ nó lúc đóng file. Bản đã gửi đi mang số
frame tạm sai → trình phát cắt cụt audio (đo được: chỉ còn 0,7 / 2,5 giây). Vì vậy frame đó bị bỏ, và dùng bitrate
cố định để trình phát nào ước tính độ dài theo bitrate cũng đúng.
"""
import io

import numpy as np
import soundfile as sf

COMPRESSION = 0.75  # libsndfile, bitrate cố định: ~96 kbps mono, đủ cho giọng nói (WAV 48 kHz là 768 kbps)
BITRATES_V1 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
BITRATES_V2 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
SAMPLE_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}  # MPEG-1 / 2 / 2.5


def frame_length(header: bytes) -> int | None:
    """Độ dài (byte) của frame MPEG Layer III mở đầu bằng `header`, None nếu đó không phải header hợp lệ."""
    if len(header) < 4 or header[0] != 0xFF or (header[1] & 0xE0) != 0xE0 or ((header[1] >> 1) & 3) != 1:
        return None
    version, bitrate_i = (header[1] >> 3) & 3, header[2] >> 4
    rate_i, padding = (header[2] >> 2) & 3, (header[2] >> 1) & 1
    if version == 1 or bitrate_i in (0, 15) or rate_i == 3:
        return None
    bitrate = (BITRATES_V1 if version == 3 else BITRATES_V2)[bitrate_i] * 1000
    return (144 if version == 3 else 72) * bitrate // SAMPLE_RATES[version][rate_i] + padding


class Mp3Encoder:
    """feed(khúc audio) → byte MP3 mới có; close() → phần còn lại. Không bao giờ trả frame Xing/Info đầu."""

    def __init__(self, sample_rate: int):
        self._buffer = io.BytesIO()
        self._sent = 0
        self._head = True  # chưa xử lý frame đầu
        self._file = sf.SoundFile(self._buffer, "w", sample_rate, 1, format="MP3", subtype="MPEG_LAYER_III",
                                  bitrate_mode="CONSTANT", compression_level=COMPRESSION)

    def _take(self) -> bytes:
        with self._buffer.getbuffer() as view:
            new = bytes(view[self._sent:])
        if self._head:
            size = frame_length(new[:4])
            if len(new) < 4 or (size is not None and len(new) < size):
                return b""  # frame đầu chưa đủ: chờ thêm
            self._head = False
            if size is not None and (b"Xing" in new[:size] or b"Info" in new[:size]):
                self._sent += size
                new = new[size:]
        self._sent += len(new)
        return new

    def feed(self, samples: np.ndarray) -> bytes:
        self._file.write(np.asarray(samples, dtype=np.float32).reshape(-1))
        return self._take()

    def close(self) -> bytes:
        if self._file.closed:
            return b""
        self._file.close()  # đẩy nốt các frame còn trong bộ mã hoá (và ghi đè frame Xing đã bỏ - không ảnh hưởng)
        return self._take()
