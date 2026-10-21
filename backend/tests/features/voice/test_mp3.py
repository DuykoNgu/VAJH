"""MP3 phát dần: frame Xing (bị ghi đè lúc đóng file) phải bị bỏ, nếu không trình phát cắt cụt audio."""
import io

import numpy as np
import soundfile as sf

from app.features.voice.mp3 import Mp3Encoder, frame_length

SR = 48000


def tone(seconds: float) -> np.ndarray:
    return (0.3 * np.sin(2 * np.pi * 220 * np.arange(int(seconds * SR)) / SR)).astype(np.float32)


def stream(audio: np.ndarray, chunk: int = 3840) -> list[bytes]:
    encoder = Mp3Encoder(SR)
    pieces = [encoder.feed(audio[i:i + chunk]) for i in range(0, len(audio), chunk)]
    return pieces + [encoder.close()]


def test_streamed_mp3_decodes_to_the_full_length():
    pieces = stream(tone(2.5))
    data = b"".join(pieces)
    assert sum(1 for p in pieces[:3] if p) >= 2                    # có byte gửi được ngay từ những khúc đầu
    assert b"Xing" not in data[:2000] and b"Info" not in data[:2000]
    decoded, rate = sf.read(io.BytesIO(data))
    assert rate == SR and 2.5 <= len(decoded) / SR <= 2.65          # đủ 2,5 s (+ đệm của bộ mã hoá), không bị cắt


def test_sentences_concatenate_into_one_valid_stream():
    data = b"".join(stream(tone(1.0))) + b"".join(stream(tone(1.5)))
    assert 2.5 <= len(sf.read(io.BytesIO(data))[0]) / SR <= 2.75


def test_frame_length_parses_mpeg1_layer3_and_rejects_garbage():
    assert frame_length(bytes([0xFF, 0xFB, 0x74, 0xC4])) == 144 * 96000 // 48000   # 96 kbps, 48 kHz, không đệm
    assert frame_length(bytes([0xFF, 0xFB, 0x70, 0xC4])) == 144 * 96000 // 44100   # cùng bitrate, 44,1 kHz
    assert frame_length(b"ID3\x04") is None and frame_length(b"\xff") is None
