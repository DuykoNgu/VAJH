from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import jobs
from app.agents import base as agents
from app.api import chat, health, me, teacher
from app.config import Settings, get_settings
from app.identity import DEV_USER_HEADER, make_identity_provider
from app.storage import cache, relational


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        agents.registry.assert_complete()  # cả 7 agent phải có (stub hoặc thật)
        await relational.open_pool(settings.database_url)
        cache.open_redis(settings.redis_url)
        jobs.configure_queue(settings.redis_url)
        try:
            yield
        finally:
            await jobs.close_queue()
            await cache.close_redis()
            await relational.close_pool()

    app = FastAPI(title="LUSIA API", lifespan=lifespan)
    app.state.identity_provider = make_identity_provider(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["*"],
        allow_headers=["Content-Type", DEV_USER_HEADER],
    )
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(chat.router)
    app.include_router(teacher.router)
    return app


app = create_app()
