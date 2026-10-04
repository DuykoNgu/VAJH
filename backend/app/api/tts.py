"""POST /tts: một câu → audio WAV tiếng Việt (công thức được đọc thành lời trước khi tổng hợp)."""
from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.ai.speech import SynthesizeRequest
from app.voice.normalize import normalize_for_speech

router = APIRouter(tags=["voice"])


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600, pattern=r"\S")


@router.post("/tts")
async def text_to_speech(request: Request, body: TtsRequest) -> Response:
    text = normalize_for_speech(body.text)
    speech = await request.app.state.tts.synthesize(SynthesizeRequest(text=text, language="vi"))
    return Response(speech.audio, media_type=speech.audio_format)
