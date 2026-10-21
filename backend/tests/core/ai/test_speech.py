import pytest
from pydantic import ValidationError

from app.core.ai.speech import SynthesizeRequest, TranscribeRequest


def test_speech_rate_out_of_range_rejected_before_provider():
    with pytest.raises(ValidationError):
        SynthesizeRequest(text="Xin chào", language="vi", speech_rate=3.0)


def test_unsupported_language_rejected():
    with pytest.raises(ValidationError):
        TranscribeRequest(audio=b"x", audio_format="audio/webm", language="en")
