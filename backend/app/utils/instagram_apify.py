"""Instagram reel transcripts via Apify actors (cloud-friendly)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_ACTOR = "crawlerbros~instagram-transcript-scraper"


def _actor_id() -> str:
    custom = settings.apify_instagram_transcript_actor.strip()
    if custom:
        return custom.replace("/", "~")
    return _DEFAULT_ACTOR


def _parse_dataset_items(items: list[Any]) -> list[dict]:
    """Normalize Apify dataset rows to {text, start, duration}."""
    segments: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        # crawlerbros/instagram-transcript-scraper — one row per segment
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

        # apify/instagram-reel-scraper — single transcript string per reel
        full = (item.get("transcript") or item.get("fullText") or "").strip()
        if full and not segments:
            segments.append({"text": full, "start": 0.0, "duration": 0.0})

    segments.sort(key=lambda s: s["start"])
    return segments


def fetch_instagram_transcript_apify(reel_url: str) -> list[dict]:
    """Run Apify Instagram transcript actor (sync) and return timed segments."""
    api_key = settings.apify_api_key.strip()
    if not api_key:
        return []

    actor = _actor_id()
    endpoint = (
        f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
        f"?token={api_key}"
    )

    body: dict[str, Any] = {
        "videoUrls": [reel_url.strip()],
        "transcriptionMethod": "auto",
        "language": "en",
    }
    # bulletproof/instagram-transcript-extractor uses `url` not videoUrls
    if "transcript-extractor" in actor:
        body = {"url": reel_url.strip(), "language": "en", "format": "json"}

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(endpoint, json=body)
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Apify Instagram transcript HTTP %s for %s: %s",
                    resp.status_code,
                    reel_url,
                    resp.text[:300],
                )
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Apify Instagram transcript failed for %s: %s", reel_url, exc)
        return []

    if not isinstance(data, list):
        logger.warning("Apify returned unexpected payload for %s", reel_url)
        return []

    segments = _parse_dataset_items(data)
    if segments:
        logger.info(
            "Instagram transcript from Apify (%s): %d segments for %s",
            actor,
            len(segments),
            reel_url,
        )
    return segments
