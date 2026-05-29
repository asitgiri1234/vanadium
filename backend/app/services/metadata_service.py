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

logger = get_logger(__name__)


@dataclass
class RawMetadata:
    platform: Platform
    title: str = "Unknown title"
    creator: str = "Unknown creator"
    follower_count: int = 0
    thumbnail: Optional[str] = None
    views: int = 0
    likes: int = 0
    comments: int = 0
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

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
        }
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

        return RawMetadata(
            platform=platform,
            title=info.get("title") or "Unknown title",
            creator=creator,
            follower_count=follower_count,
            thumbnail=info.get("thumbnail"),
            views=_as_int(info.get("view_count")),
            likes=_as_int(info.get("like_count")),
            comments=_as_int(info.get("comment_count")),
            duration_seconds=_as_int(info.get("duration")),
            upload_date=_format_upload_date(info.get("upload_date")),
            hashtags=hashtags,
            description=description,
            raw=info,
        )


metadata_service = MetadataService()
