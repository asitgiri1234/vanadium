"""YouTube transcripts via SerpApi (works from datacenter IPs)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SERPAPI_SEARCH = "https://serpapi.com/search"


def _parse_serpapi_response(data: dict[str, Any]) -> list[dict]:
    transcript = data.get("transcript")
    if isinstance(transcript, str):
        text = transcript.strip()
        if text:
            return [{"text": text, "start": 0.0, "duration": 0.0}]
        return []

    if not isinstance(transcript, list):
        return []

    segments: list[dict] = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        snippet = (item.get("snippet") or item.get("text") or "").strip()
        if not snippet:
            continue
        start_ms = item.get("start_ms")
        end_ms = item.get("end_ms")
        try:
            start = float(start_ms) / 1000.0 if start_ms is not None else 0.0
        except (TypeError, ValueError):
            start = 0.0
        duration = 0.0
        if end_ms is not None and start_ms is not None:
            try:
                duration = max(0.0, (float(end_ms) - float(start_ms)) / 1000.0)
            except (TypeError, ValueError):
                duration = 0.0
        segments.append({"text": snippet, "start": start, "duration": duration})
    return segments


def fetch_youtube_transcript_serpapi(video_id: str) -> list[dict]:
    """Fetch timed transcript snippets from SerpApi YouTube Video Transcript engine."""
    api_key = settings.serp_api_key.strip()
    if not api_key:
        return []

    param_sets: list[dict[str, str]] = [
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "api_key": api_key,
            "language_code": "en",
            "type": "asr",
        },
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "api_key": api_key,
            "language_code": "en",
        },
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "api_key": api_key,
        },
    ]

    for params in param_sets:
        try:
            with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                resp = client.get(_SERPAPI_SEARCH, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SerpApi transcript failed for %s (%s): %s",
                video_id,
                params.get("type") or "default",
                exc,
            )
            continue

        meta = data.get("search_metadata") or {}
        if meta.get("status") == "Error":
            logger.warning(
                "SerpApi transcript error for %s: %s",
                video_id,
                data.get("error") or meta,
            )
            continue

        segments = _parse_serpapi_response(data)
        if segments:
            logger.info(
                "YouTube captions from SerpApi for %s: %d segments",
                video_id,
                len(segments),
            )
            return segments

    return []
