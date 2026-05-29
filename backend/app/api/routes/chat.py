"""Streaming RAG chat endpoint (Server-Sent Events)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest
from app.rag.chat_service import chat_service

router = APIRouter(tags=["chat"])


async def _event_stream(analysis_id: str, message: str) -> AsyncIterator[dict]:
    """Map internal chat events to SSE ``{event, data}`` frames."""
    async for ev in chat_service.stream(analysis_id, message):
        kind = ev.get("type")
        if kind == "token":
            yield {"event": "token", "data": json.dumps({"text": ev["text"]})}
        elif kind == "citations":
            yield {"event": "citations", "data": json.dumps(ev["data"])}
        elif kind == "error":
            yield {"event": "error", "data": json.dumps({"detail": ev["detail"]})}
        elif kind == "done":
            yield {"event": "done", "data": json.dumps({"message_id": ev["message_id"]})}


@router.post("/chat")
async def chat(payload: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(
        _event_stream(payload.analysis_id, payload.message),
        media_type="text/event-stream",
    )
