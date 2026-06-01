"""Instagram data via Apify apify/instagram-scraper (sync dataset run)."""

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

# Official actor — REST URL uses tilde instead of slash.
ACTOR_ID = "apify~instagram-scraper"
APIFY_RUN_SYNC_DATASET = (
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
)

_CACHE_TTL_SEC = 300.0
_dataset_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass
class InstagramApifyResult:
    """Parsed apify/instagram-scraper dataset for one reel/post URL."""

    post: dict[str, Any] | None = None
    comments: list[dict[str, Any]] = field(default_factory=list)
    dataset_items: list[dict[str, Any]] = field(default_factory=list)


def _build_input(
    reel_url: str,
    *,
    results_type: str = "posts",
    results_limit: int = 1,
) -> dict[str, Any]:
    return {
        "directUrls": [reel_url.strip()],
        "resultsType": results_type,
        "resultsLimit": results_limit,
    }


def _run_sync_dataset(
    reel_url: str,
    *,
    results_type: str = "posts",
    results_limit: int = 1,
) -> list[dict[str, Any]]:
    """POST run-sync-get-dataset-items; token from APIFY_API_KEY env only."""
    api_key = settings.apify_api_key.strip()
    if not api_key:
        return []

    body = _build_input(
        reel_url,
        results_type=results_type,
        results_limit=results_limit,
    )

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                APIFY_RUN_SYNC_DATASET,
                params={"token": api_key},
                json=body,
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Apify %s HTTP %s (%s) for %s: %s",
                    ACTOR_ID,
                    resp.status_code,
                    results_type,
                    reel_url,
                    resp.text[:400],
                )
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Apify %s failed (%s) for %s: %s",
            ACTOR_ID,
            results_type,
            reel_url,
            exc,
        )
        return []

    if not isinstance(data, list):
        logger.warning("Apify %s unexpected payload for %s", ACTOR_ID, reel_url)
        return []

    logger.info(
        "Apify %s ok (%s): %d dataset items for %s",
        ACTOR_ID,
        results_type,
        len(data),
        reel_url,
    )
    return data


def _cache_key(url: str) -> str:
    return url.strip().split("?")[0].rstrip("/")


def _get_cached_dataset(url: str) -> list[dict[str, Any]]:
    key = _cache_key(url)
    now = time.monotonic()
    cached = _dataset_cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    posts = _run_sync_dataset(url, results_type="posts", results_limit=1)
    comments = _run_sync_dataset(url, results_type="comments", results_limit=50)
    combined = posts + [
        c for c in comments if isinstance(c, dict) and c not in posts
    ]
    _dataset_cache[key] = (now, combined)
    return combined


def _is_comment_row(item: dict[str, Any]) -> bool:
    return bool(item.get("postId")) and bool(item.get("text"))


def _is_post_row(item: dict[str, Any]) -> bool:
    if _is_comment_row(item):
        return False
    return (
        item.get("type") in ("Video", "Image", "Sidecar", "Reel", "GraphVideo")
        or item.get("likesCount") is not None
        or item.get("shortCode")
    )


def parse_instagram_scraper_dataset(items: list[Any]) -> InstagramApifyResult:
    """Split dataset into post metrics and comment rows."""
    result = InstagramApifyResult(dataset_items=[])

    for raw in items:
        if not isinstance(raw, dict):
            continue
        result.dataset_items.append(raw)

        if _is_comment_row(raw):
            result.comments.append(raw)
            continue

        if _is_post_row(raw) and result.post is None:
            result.post = raw
            embedded = raw.get("latestComments") or []
            if isinstance(embedded, list):
                for comment in embedded:
                    if isinstance(comment, dict) and comment not in result.comments:
                        result.comments.append(comment)

    return result


def fetch_instagram_apify(url: str) -> InstagramApifyResult:
    """Run apify/instagram-scraper (posts + comments) and parse the dataset."""
    if not settings.apify_api_key.strip():
        return InstagramApifyResult()
    items = _get_cached_dataset(url)
    return parse_instagram_scraper_dataset(items)


def apify_result_to_raw(url: str, parsed: InstagramApifyResult) -> RawMetadata | None:
    """Map scraper post row to RawMetadata (likes, comments count, views, etc.)."""
    post = parsed.post
    if not post:
        return None

    caption = (post.get("caption") or post.get("title") or "").strip()
    owner = post.get("ownerUsername") or post.get("username") or "Unknown creator"
    handle = str(owner).lstrip("@")

    likes = post.get("likesCount")
    comments_count = post.get("commentCount") or post.get("commentsCount")
    views = (
        post.get("videoViewCount")
        or post.get("videoPlayCount")
        or post.get("playCount")
        or 0
    )

    duration = post.get("videoDuration")
    duration_seconds = 0
    if duration is not None:
        try:
            duration_seconds = int(float(duration))
        except (TypeError, ValueError):
            duration_seconds = 0

    video_url = post.get("videoUrl") or post.get("video_url")
    thumb = post.get("displayUrl") or post.get("thumbnailUrl")

    return RawMetadata(
        platform=Platform.instagram,
        title=caption[:300] if caption else "Instagram Reel",
        creator=handle or str(owner),
        creator_url=f"https://www.instagram.com/{handle}/" if handle else None,
        thumbnail=str(thumb) if thumb else None,
        views=int(views) if views else 0,
        likes=int(likes) if likes is not None else None,
        comments=int(comments_count) if comments_count is not None else None,
        duration_seconds=duration_seconds,
        description=caption,
        raw={
            "apify_post": post,
            "apify_comments": parsed.comments,
            "ig_video_urls": [video_url] if video_url else [],
            "thumbnail_url": thumb,
        },
    )


def fetch_instagram_apify_metadata(url: str) -> RawMetadata | None:
    """Post metrics + embedded comments from apify/instagram-scraper."""
    parsed = fetch_instagram_apify(url)
    meta = apify_result_to_raw(url, parsed)
    if meta:
        logger.info(
            "Instagram metadata from Apify: likes=%s comments=%s views=%s (%d comment rows)",
            meta.likes,
            meta.comments,
            meta.views,
            len(parsed.comments),
        )
    return meta


def fetch_instagram_transcript_apify(reel_url: str) -> list[dict]:
    """Transcript segments — caption text from scraper (no timed captions on this actor)."""
    parsed = fetch_instagram_apify(reel_url)
    post = parsed.post
    if not post:
        return []

    caption = (post.get("caption") or "").strip()
    if not caption:
        return []

    logger.info(
        "Instagram caption transcript from Apify (%s): %d chars for %s",
        ACTOR_ID,
        len(caption),
        reel_url,
    )
    return [{"text": caption, "start": 0.0, "duration": 0.0}]
