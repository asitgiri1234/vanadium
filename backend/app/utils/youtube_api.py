"""YouTube Data API v3 metadata fallback (optional YOUTUBE_API_KEY)."""

from __future__ import annotations

import re

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Platform
from app.models.raw_metadata import RawMetadata
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

_ISO8601_DURATION = re.compile(
    r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def _parse_iso8601_duration(raw: str) -> int:
    match = _ISO8601_DURATION.fullmatch(raw or "")
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def fetch_youtube_api_metadata(url: str) -> RawMetadata | None:
    """Fetch rich metadata via YouTube Data API when an API key is configured."""
    api_key = settings.youtube_api_key.strip()
    if not api_key:
        return None

    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": video_id,
                    "key": api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube Data API failed for %s: %s", url, exc)
        return None

    if not items:
        return None

    item = items[0]
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    content = item.get("contentDetails") or {}

    channel_id = snippet.get("channelId")
    thumbs = snippet.get("thumbnails") or {}
    thumb = (
        (thumbs.get("maxres") or thumbs.get("high") or thumbs.get("medium") or {}).get("url")
    )

    def stat_int(key: str) -> int | None:
        val = stats.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    published = snippet.get("publishedAt") or ""
    upload_date = published[:10] if len(published) >= 10 else None

    follower_count = 0
    if channel_id:
        follower_count = _fetch_channel_subscriber_count(api_key, channel_id) or 0

    return RawMetadata(
        platform=Platform.youtube,
        title=snippet.get("title") or "Unknown title",
        creator=snippet.get("channelTitle") or "Unknown creator",
        creator_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
        follower_count=follower_count,
        thumbnail=thumb,
        views=stat_int("viewCount") or 0,
        likes=stat_int("likeCount"),
        comments=stat_int("commentCount"),
        duration_seconds=_parse_iso8601_duration(content.get("duration") or ""),
        upload_date=upload_date,
        description=snippet.get("description") or "",
    )


def _fetch_channel_subscriber_count(api_key: str, channel_id: str) -> int | None:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "statistics",
                    "id": channel_id,
                    "key": api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube channel stats failed for %s: %s", channel_id, exc)
        return None

    if not items:
        return None

    stats = items[0].get("statistics") or {}
    val = stats.get("subscriberCount")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def fetch_youtube_channel_metadata(channel_id: str) -> RawMetadata | None:
    """Fetch subscriber count when we have a channel id but no full video API call."""
    api_key = settings.youtube_api_key.strip()
    if not api_key or not channel_id:
        return None

    followers = _fetch_channel_subscriber_count(api_key, channel_id)
    if not followers:
        return None

    return RawMetadata(
        platform=Platform.youtube,
        follower_count=followers,
        creator_url=f"https://www.youtube.com/channel/{channel_id}",
    )
