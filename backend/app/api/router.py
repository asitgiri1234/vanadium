"""Aggregate all route modules under the ``/api`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import chat, debug, health, ingest, media

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(debug.router)
api_router.include_router(ingest.router)
api_router.include_router(chat.router)
api_router.include_router(media.router)
