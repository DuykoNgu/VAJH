import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.core import jobs
from app.core.ai.llm import make_llm
from app.core.ai.speech import make_tts
from app.core.identity import DEV_USER_HEADER, make_identity_provider
from app.core.rag.embeddings import make_embeddings, warm_up
from app.core.storage import cache, relational
from app.core.storage.files import make_file_store
from app.features.curation import router as curation
from app.features.documents import router as documents
from app.features.health import router as health
from app.features.learning import router as learning
from app.features.learning.service import build_agents
from app.features.me import router as me
from app.features.monitor import router as monitor
from app.features.teacher import router as teacher
from app.features.voice import router as voice


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agents = build_agents(app.state.llm, app.state.embeddings)  # đủ 7 agent, thay stub bằng bản thật
        await relational.open_pool(settings.database_url)
        cache.open_redis(settings.redis_url)
        jobs.configure_queue(settings.redis_url)
        warm = getattr(app.state.tts, "warm_up", None)
        # Nạp nền model TTS và embedding: câu hỏi đầu tiên của học sinh không phải chờ
        warming = asyncio.gather(warm() if warm else asyncio.sleep(0), warm_up(app.state.embeddings))
        try:
            yield
        finally:
            if warming:
                warming.cancel()
            await jobs.close_queue()
            await cache.close_redis()
            await relational.close_pool()

    app = FastAPI(title="LUSIA API", lifespan=lifespan)
    app.state.settings = settings
    app.state.identity_provider = make_identity_provider(settings)
    app.state.files = make_file_store(settings)
    app.state.llm = make_llm(settings)
    app.state.embeddings = make_embeddings(settings)
    app.state.tts = make_tts(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["*"],
        allow_headers=["Content-Type", DEV_USER_HEADER],
    )
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(documents.router)
    app.include_router(voice.router)
    app.include_router(learning.router)
    app.include_router(teacher.router)
    app.include_router(curation.router)
    app.include_router(monitor.router)
    return app


app = create_app()
