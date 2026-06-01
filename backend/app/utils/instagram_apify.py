"""Instagram reel transcripts via Apify crawlerbros/instagram-transcript-scraper."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Developer actor ID in Apify REST URLs: slash → tilde (~)
ACTOR_ID = "crawlerbros~instagram-transcript-scraper"
APIFY_RUN_SYNC_DATASET = (
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
)


def _build_input(reel_url: str) -> dict[str, Any]:
    """Input for crawlerbros/instagram-transcript-scraper."""
    url = reel_url.strip()
    return {
        "startUrls": [{"url": url}],
        # Actor OpenAPI also documents videoUrls; include for compatibility.
        "videoUrls": [url],
        "transcriptionMethod": "auto",
        "language": "en",
    }


def _parse_dataset_items(items: list[Any]) -> list[dict]:
    """Normalize Apify dataset rows to {text, start, duration}."""
    segments: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        if item.get("errMsg"):
            logger.warning("Apify segment error: %s", item.get("errMsg"))
            continue

        seg_text = (item.get("segmentText") or item.get("text") or "").strip()
        if seg_text:
            try:
                start = float(item.get("segmentStart") or item.get("start") or 0.0)
            except (TypeError, ValueError):
                start = 0.0
            try:
                end = float(item.get("segmentEnd") or item.get("end") or start)
            except (TypeError, ValueError):
                end = start
            segments.append(
                {
                    "text": seg_text,
                    "start": start,
                    "duration": max(0.0, end - start),
                }
            )
            continue

        full = (item.get("fullText") or item.get("transcript") or "").strip()
        if full and not segments:
            segments.append({"text": full, "start": 0.0, "duration": 0.0})

    segments.sort(key=lambda s: s["start"])
    return segments


def fetch_instagram_transcript_apify(reel_url: str) -> list[dict]:
    """Run crawlerbros/instagram-transcript-scraper (sync) and return timed segments."""
    api_key = settings.apify_api_key.strip()
    if not api_key:
        return []

    body = _build_input(reel_url)

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                APIFY_RUN_SYNC_DATASET,
                params={"token": api_key},
                json=body,
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Apify %s HTTP %s for %s: %s",
                    ACTOR_ID,
                    resp.status_code,
                    reel_url,
                    resp.text[:400],
                )
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Apify %s failed for %s: %s", ACTOR_ID, reel_url, exc)
        return []

    if not isinstance(data, list):
        logger.warning("Apify %s returned unexpected payload for %s", ACTOR_ID, reel_url)
        return []

    segments = _parse_dataset_items(data)
    if segments:
        logger.info(
            "Instagram transcript from Apify (%s): %d segments for %s",
            ACTOR_ID,
            len(segments),
            reel_url,
        )
    return segments
