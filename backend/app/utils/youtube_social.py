"""Third-party YouTube stats (works when YouTube blocks datacenter IPs)."""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_proxy import fetch_frontend_proxy

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
    data: dict | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                resp = client.get(
                    f"{_SOCIALCOUNTS_API}/{video_id}",
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": "https://socialcounts.org/",
                        "Origin": "https://socialcounts.org",
                    },
                )
                if resp.status_code == 403 and is_youtube_cloud_host():
                    break
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
        if last_exc and not is_youtube_cloud_host():
            logger.warning("YouTube SocialCounts API failed for %s: %s", video_id, last_exc)
            return None

    if data is None and is_youtube_cloud_host():
        proxy = fetch_frontend_proxy("stats", video_id)
        if proxy and int(proxy.get("status") or 0) == 200:
            data = proxy.get("data") if isinstance(proxy.get("data"), dict) else None
        if not data:
            logger.warning("YouTube SocialCounts proxy failed for %s", video_id)
            return None
    elif data is None:
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
