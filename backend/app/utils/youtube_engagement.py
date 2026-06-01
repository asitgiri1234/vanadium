"""Third-party YouTube engagement stats (works when YouTube blocks datacenter IPs)."""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

# Public stats API — view counts + likes when direct YouTube access is blocked.
_RYD_API = "https://returnyoutubedislikeapi.com/votes"


def fetch_youtube_engagement_stats(url: str) -> RawMetadata | None:
    """Fetch views/likes from Return YouTube Dislike API (not YouTube-owned)."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                _RYD_API,
                params={"videoId": video_id},
                headers={"User-Agent": "Vanadium/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube engagement API failed for %s: %s", video_id, exc)
        return None

    views = int(data.get("viewCount") or 0)
    if views <= 0:
        return None

    likes_raw = data.get("likes")
    likes: int | None
    try:
        likes = int(likes_raw) if likes_raw is not None else None
    except (TypeError, ValueError):
        likes = None

    logger.info("YouTube engagement API: views=%s likes=%s for %s", views, likes, video_id)

    return RawMetadata(
        platform=Platform.youtube,
        views=views,
        likes=likes,
    )
