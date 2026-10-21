"""Hợp đồng Speech-to-Text / Text-to-Speech. Provider thật được thêm ở change `voice-loop` (sau spike S2/S3)."""
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field

Language = Literal["vi", "ja"]


class TranscribeRequest(BaseModel):
    audio: bytes
    audio_format: str                   # MIME, vd. "audio/webm"
    language: Language
    vocabulary_hint: str | None = None  # thuật ngữ của bài học, giúp nhận dạng đúng


@dataclass
class Transcript:
    text: str
    language: Language


class SynthesizeRequest(BaseModel):
    text: str
    language: Language
    speech_rate: float = Field(1.0, ge=0.5, le=2.0)  # khớp students.speech_rate


@dataclass
class Speech:
    audio: bytes
    audio_format: str


class STT(Protocol):
    async def transcribe(self, request: TranscribeRequest) -> Transcript: ...


class TTS(Protocol):
    stream_format: str  # kiểu MIME của stream()

    async def synthesize(self, request: SynthesizeRequest) -> Speech: ...

    def stream(self, text: str) -> AsyncIterator[bytes]:
        """Audio của một câu, gửi dần trong lúc tổng hợp (ghép nhiều câu liên tiếp vẫn là một luồng hợp lệ)."""


def make_stt(settings) -> STT:
    from app.core.ai.fakes import FakeSTT

    return FakeSTT()  # chỉ có "fake" cho tới voice-loop


def make_tts(settings) -> TTS:
    if settings.tts_provider == "zerotts":
        from app.features.voice.tts import ZeroTTSEngine

        return ZeroTTSEngine(settings)
    from app.core.ai.fakes import FakeTTS

    return FakeTTS()
