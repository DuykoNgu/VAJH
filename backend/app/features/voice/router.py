"""Đọc thành tiếng: công thức được đọc thành lời trước khi tổng hợp.

POST /tts/stream: cả lượt nói (các câu theo thứ tự) → MỘT luồng MP3 phát dần (trình duyệt phát qua Media Source).
POST /tts: một câu → WAV trọn vẹn.
"""
from typing import Annotated

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.core.ai.speech import SynthesizeRequest
from app.features.voice.normalize import speakable

router = APIRouter(tags=["voice"])
Sentence = Annotated[str, Field(min_length=1, max_length=600, pattern=r"\S")]


class TtsRequest(BaseModel):
    text: Sentence


class StreamRequest(BaseModel):
    sentences: list[Sentence] = Field(min_length=1, max_length=60)


@router.post("/tts")
async def text_to_speech(request: Request, body: TtsRequest) -> Response:
    text = speakable(body.text)
    speech = await request.app.state.tts.synthesize(SynthesizeRequest(text=text, language="vi"))
    return Response(speech.audio, media_type=speech.audio_format)


@router.post("/tts/stream")
async def stream_speech(request: Request, body: StreamRequest) -> StreamingResponse:
    """Tổng hợp lần lượt đúng thứ tự, gửi audio ngay khi có; trình duyệt ngắt kết nối thì dừng tổng hợp."""
    tts = request.app.state.tts

    async def audio():
        for sentence in body.sentences:
            async for piece in tts.stream(speakable(sentence)):
                yield piece

    return StreamingResponse(audio(), media_type=tts.stream_format, headers={"Cache-Control": "no-store"})
