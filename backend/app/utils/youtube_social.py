"""Third-party YouTube stats (works when YouTube blocks datacenter IPs)."""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

_RYD_API = "https://returnyoutubedislikeapi.com/votes"
_SOCIALCOUNTS_API = "https://api.socialcounts.org/youtube-video-live-view-count"


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _fetch_ryd(video_id: str) -> RawMetadata | None:
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
        logger.warning("YouTube RYD API failed for %s: %s", video_id, exc)
        return None

    views = int(data.get("viewCount") or 0)
    if views <= 0:
        return None

    return RawMetadata(
        platform=Platform.youtube,
        views=views,
        likes=_safe_int(data.get("likes")),
    )


def _fetch_socialcounts(video_id: str) -> RawMetadata | None:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.get(
                    f"{_SOCIALCOUNTS_API}/{video_id}",
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (compatible; Vanadium/1.0; +https://github.com/asitgiri1234/vanadium)"
                        ),
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "YouTube SocialCounts API attempt %s failed for %s: %s",
                attempt + 1,
                video_id,
                exc,
            )
    else:
        if last_exc:
            logger.warning("YouTube SocialCounts API failed for %s: %s", video_id, last_exc)
        return None

    counters_root = data.get("counters") or {}
    counters = counters_root.get("api") or counters_root.get("estimation") or {}
    views = int(counters.get("viewCount") or 0)
    comments = _safe_int(counters.get("commentCount"))
    likes = _safe_int(counters.get("likeCount"))

    if views <= 0 and comments is None:
        return None

    return RawMetadata(
        platform=Platform.youtube,
        views=views,
        likes=likes,
        comments=comments,
    )


def fetch_youtube_social_metadata(url: str) -> RawMetadata | None:
    """Aggregate views/likes/comments from third-party APIs (not youtube.com)."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    ryd = _fetch_ryd(video_id)
    social = _fetch_socialcounts(video_id)

    if not ryd and not social:
        return None

    if not ryd:
        logger.info("YouTube social metadata from SocialCounts for %s", video_id)
        return social
    if not social:
        logger.info("YouTube social metadata from RYD for %s", video_id)
        return ryd

    # Prefer SocialCounts for comments; merge both sources.
    merged = RawMetadata(
        platform=Platform.youtube,
        views=social.views or ryd.views,
        likes=social.likes if social.likes is not None else ryd.likes,
        comments=social.comments,
    )
    logger.info(
        "YouTube social metadata merged for %s (views=%s comments=%s)",
        video_id,
        merged.views,
        merged.comments,
    )
    return merged
