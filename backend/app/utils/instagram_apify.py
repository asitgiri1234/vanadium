"""Instagram transcripts + metrics via Apify crawlerbros/instagram-transcript-scraper."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform

logger = get_logger(__name__)

# Developer actor — slash → tilde in REST URLs.
ACTOR_ID = "crawlerbros~instagram-transcript-scraper"
APIFY_RUN_SYNC_DATASET = (
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
)

_CACHE_TTL_SEC = 300.0
_dataset_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass
class InstagramApifyResult:
    """Parsed crawlerbros transcript-scraper dataset."""

    post: dict[str, Any] | None = None
    comments: list[dict[str, Any]] = field(default_factory=list)
    dataset_items: list[dict[str, Any]] = field(default_factory=list)
    full_text: str = ""


def _build_input(reel_url: str) -> dict[str, Any]:
    """Force Whisper audio transcription on the crawlerbros actor."""
    return {
        "videoUrls": [reel_url.strip()],
        "transcriptionMethod": "whisper",
        "whisperModel": "base",
        "language": "en",
    }


def _run_sync_dataset(reel_url: str) -> list[dict[str, Any]]:
    """POST run-sync-get-dataset-items; token from APIFY_API_KEY env only."""
    api_key = settings.apify_api_key.strip()
    if not api_key:
        return []

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                APIFY_RUN_SYNC_DATASET,
                params={"token": api_key},
                json=_build_input(reel_url),
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
        logger.warning("Apify %s unexpected payload for %s", ACTOR_ID, reel_url)
        return []

    logger.info("Apify %s ok: %d dataset items for %s", ACTOR_ID, len(data), reel_url)
    return data


def _cache_key(url: str) -> str:
    return url.strip().split("?")[0].rstrip("/")


def _get_cached_dataset(url: str) -> list[dict[str, Any]]:
    key = _cache_key(url)
    now = time.monotonic()
    cached = _dataset_cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    items = _run_sync_dataset(url)
    _dataset_cache[key] = (now, items)
    return items


def _parse_transcript_segments(items: list[Any]) -> list[dict]:
    """Build segments from segmentText rows, else a single block from fullText (not title/caption)."""
    timed: list[dict] = []
    full_text_parts: list[str] = []

    for raw in items:
        if not isinstance(raw, dict):
            continue
        if raw.get("errMsg"):
            logger.warning("Apify segment error: %s", raw.get("errMsg"))
            continue

        seg_text = (raw.get("segmentText") or "").strip()
        if seg_text:
            try:
                start = float(raw.get("segmentStart") or 0.0)
            except (TypeError, ValueError):
                start = 0.0
            try:
                end = float(raw.get("segmentEnd") or start)
            except (TypeError, ValueError):
                end = start
            timed.append(
                {
                    "text": seg_text,
                    "start": start,
                    "duration": max(0.0, end - start),
                }
            )

        spoken = (raw.get("fullText") or "").strip()
        if spoken and spoken not in full_text_parts:
            full_text_parts.append(spoken)

    if timed:
        timed.sort(key=lambda s: s["start"])
        return timed

    if full_text_parts:
        # Prefer longest fullText (duplicate on each segment row).
        full = max(full_text_parts, key=len)
        return [{"text": full, "start": 0.0, "duration": 0.0}]

    return []


def parse_instagram_transcript_dataset(items: list[Any]) -> InstagramApifyResult:
    """Parse post metrics and fullText from crawlerbros dataset rows."""
    result = InstagramApifyResult(dataset_items=[])
    full_text_candidates: list[str] = []

    for raw in items:
        if not isinstance(raw, dict):
            continue
        result.dataset_items.append(raw)

        spoken = (raw.get("fullText") or "").strip()
        if spoken and spoken not in full_text_candidates:
            full_text_candidates.append(spoken)

        if result.post is None and (
            raw.get("likeCount") is not None
            or raw.get("videoUrl")
            or raw.get("url")
        ):
            result.post = raw

    if full_text_candidates:
        result.full_text = max(full_text_candidates, key=len)

    return result


def fetch_instagram_apify(url: str) -> InstagramApifyResult:
    """Run crawlerbros/instagram-transcript-scraper and parse the dataset."""
    if not settings.apify_api_key.strip():
        return InstagramApifyResult()
    return parse_instagram_transcript_dataset(_get_cached_dataset(url))


def apify_result_to_raw(url: str, parsed: InstagramApifyResult) -> RawMetadata | None:
    """Map scraper row to RawMetadata (metrics only — not title/caption for transcript)."""
    post = parsed.post
    if not post:
        return None

    # Post title for UI: IG caption in `title` field from actor (not used as transcript).
    display_title = (post.get("title") or "").strip()
    owner = post.get("userName") or post.get("userFullName") or "Unknown creator"
    handle = str(owner).lstrip("@")

    likes = post.get("likeCount")
    comments_count = post.get("commentCount")
    views = post.get("play_count") or post.get("videoViewCount") or 0

    duration = post.get("video_duration") or post.get("videoDuration")
    duration_seconds = 0
    if duration is not None:
        try:
            duration_seconds = int(float(duration))
        except (TypeError, ValueError):
            duration_seconds = 0

    video_url = post.get("videoUrl")
    thumb = post.get("img") or post.get("thumbnail_url")

    return RawMetadata(
        platform=Platform.instagram,
        title=display_title[:300] if display_title else "Instagram Reel",
        creator=handle or str(owner),
        creator_url=f"https://www.instagram.com/{handle}/" if handle else None,
        thumbnail=str(thumb) if thumb else None,
        views=int(views) if views else 0,
        likes=int(likes) if likes is not None else None,
        comments=int(comments_count) if comments_count is not None else None,
        duration_seconds=duration_seconds,
        description=display_title,
        raw={
            "apify_post": post,
            "apify_full_text": parsed.full_text,
            "ig_video_urls": [video_url] if video_url else [],
            "thumbnail_url": thumb,
        },
    )


def fetch_instagram_apify_metadata(url: str) -> RawMetadata | None:
    """Likes, comments, views from crawlerbros transcript-scraper metadata fields."""
    parsed = fetch_instagram_apify(url)
    meta = apify_result_to_raw(url, parsed)
    if meta:
        logger.info(
            "Instagram metadata from Apify (%s): likes=%s comments=%s views=%s",
            ACTOR_ID,
            meta.likes,
            meta.comments,
            meta.views,
        )
    return meta


def fetch_instagram_transcript_apify(reel_url: str) -> list[dict]:
    """Spoken transcript from fullText / segmentText (never title or caption)."""
    items = _get_cached_dataset(reel_url)
    segments = _parse_transcript_segments(items)
    if segments:
        logger.info(
            "Instagram transcript from Apify (%s): %d segments for %s",
            ACTOR_ID,
            len(segments),
            reel_url,
        )
    return segments
