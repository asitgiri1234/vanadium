"""FastAPI application factory for Vanadium."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Vanadium API",
        description="AI-powered content intelligence for creators.",
        version=__version__,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"name": "Vanadium API", "version": __version__, "docs": "/docs"}

    logger.info(
        "Vanadium API %s ready (provider=%s, llm=%s, whisper=%s, visual=%s)",
        __version__,
        settings.llm_provider,
        settings.llm_configured,
        settings.enable_whisper,
        settings.enable_visual,
    )
    return app


app = create_app()
