"""Giọng nói: STT, TTS (ZeroTTS)."""
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator

from app.config.core import CoreConfig
from app.config.paths import BACKEND_DIR, absolute


class VoiceConfig(CoreConfig):
    stt_provider: Literal["fake"] = "fake"
    tts_provider: Literal["zerotts", "fake"] | None = None
    zerotts_model_dir: Path = BACKEND_DIR / "data" / "models" / "zerotts"
    zerotts_voice: str = "baotrang"

    _zerotts_model_dir = field_validator("zerotts_model_dir")(absolute)

    @model_validator(mode="after")
    def _voice_defaults(self):
        self.tts_provider = self.tts_provider or ("fake" if self.app_env == "test" else "zerotts")
        return self
