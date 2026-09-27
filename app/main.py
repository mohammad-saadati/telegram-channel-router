"""FastAPI entry point: ``uvicorn app.main:app --reload``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import agents, health, workflows
from app.core.config import Settings, get_settings
from app.core.container import build_container
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = build_container(settings)
        try:
            yield
        finally:
            await app.state.container.aclose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(workflows.router)
    return app


app = create_app()
