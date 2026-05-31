"""Metadata extraction.

Uses ``yt-dlp`` (no download) to pull a rich, platform-agnostic metadata blob
for both YouTube and Instagram. Anything that cannot be resolved falls back to
sensible defaults so ingestion never hard-fails on a single missing field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.logging import get_logger
from app.models.schemas import Platform
from app.utils.text import extract_hashtags
from app.utils.url_utils import detect_platform
from app.utils.ytdlp import apply_cookie_options

logger = get_logger(__name__)


@dataclass
class RawMetadata:
    platform: Platform
    title: str = "Unknown title"
    creator: str = "Unknown creator"
    creator_url: str | None = None
    follower_count: int = 0
    thumbnail: Optional[str] = None
    views: int = 0
    likes: int | None = None
    comments: int | None = None
    duration_seconds: int = 0
    upload_date: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)
    description: str = ""
    # The raw yt-dlp info dict, reused by the transcript service to avoid a
    # second network round-trip.
    raw: dict[str, Any] = field(default_factory=dict)


def _as_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _as_metric_int(value: Any) -> int | None:
    """Parse engagement counts; None when hidden (yt-dlp often returns -1 for IG)."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


def _creator_profile_url(info: dict[str, Any], platform: Platform) -> str | None:
    """Best-effort profile/channel link for the uploader."""
    direct = info.get("uploader_url") or info.get("channel_url")
    if direct:
        return str(direct)

    if platform == Platform.instagram:
        handle = info.get("uploader_id") or info.get("channel")
        if handle:
            return f"https://www.instagram.com/{str(handle).lstrip('@')}/"

    if platform == Platform.youtube:
        channel_id = info.get("channel_id")
        if channel_id:
            return f"https://www.youtube.com/channel/{channel_id}"
        handle = info.get("uploader_id") or info.get("channel")
        if handle:
            clean = str(handle).lstrip("@")
            return f"https://www.youtube.com/@{clean}"

    return None


def _format_upload_date(raw_date: Any) -> Optional[str]:
    """yt-dlp returns YYYYMMDD; convert to ISO YYYY-MM-DD."""
    s = str(raw_date or "")
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


class MetadataService:
    def fetch(self, url: str) -> RawMetadata:
        platform = detect_platform(url)
        try:
            return self._fetch_with_ytdlp(url, platform)
        except Exception as exc:  # noqa: BLE001 - extraction is best-effort
            logger.warning("Metadata extraction failed for %s: %s", url, exc)
            return RawMetadata(platform=platform)

    def _fetch_with_ytdlp(self, url: str, platform: Platform) -> RawMetadata:
        # Imported lazily so the package isn't required just to import the app.
        from yt_dlp import YoutubeDL

        opts = apply_cookie_options(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
            }
        )
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        info = info or {}
        description = info.get("description") or ""
        tags = info.get("tags") or []

        # Merge explicit tags with hashtags parsed from the description/caption.
        hashtags: list[str] = []
        for t in tags:
            tag = t if str(t).startswith("#") else f"#{t}"
            if tag not in hashtags:
                hashtags.append(tag)
        for tag in extract_hashtags(description):
            if tag not in hashtags:
                hashtags.append(tag)

        creator = (
            info.get("uploader")
            or info.get("channel")
            or info.get("creator")
            or "Unknown creator"
        )
        follower_count = _as_int(
            info.get("channel_follower_count") or info.get("uploader_subscriber_count")
        )

        # Instagram reels often expose plays under ``play_count`` rather than
        # ``view_count`` (and sometimes neither, in yt-dlp's webpage path).
        views = _as_int(info.get("view_count") or info.get("play_count"))
        likes = _as_metric_int(info.get("like_count"))
        comments = _as_metric_int(info.get("comment_count"))

        # Instagram often omits or zeroes like_count when likes are hidden.
        if platform == Platform.instagram:
            if info.get("like_count") is None or likes == 0:
                likes = None

        return RawMetadata(
            platform=platform,
            title=info.get("title") or "Unknown title",
            creator=creator,
            creator_url=_creator_profile_url(info, platform),
            follower_count=follower_count,
            thumbnail=info.get("thumbnail"),
            views=views,
            likes=likes,
            comments=comments,
            duration_seconds=_as_int(info.get("duration")),
            upload_date=_format_upload_date(info.get("upload_date")),
            hashtags=hashtags,
            description=description,
            raw=info,
        )


metadata_service = MetadataService()
