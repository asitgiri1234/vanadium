"""Health / capability probe."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        version=__version__,
        llm_provider=settings.llm_provider,
        llm_configured=settings.llm_configured,
        openai_configured=settings.openai_configured,
        groq_configured=settings.groq_configured,
        whisper_enabled=settings.enable_whisper,
        visual_enabled=settings.enable_visual,
    )
