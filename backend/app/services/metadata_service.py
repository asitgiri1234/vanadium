"""Metadata extraction.

Uses ``yt-dlp`` (no download) to pull a rich, platform-agnostic metadata blob
for both YouTube and Instagram. Anything that cannot be resolved falls back to
sensible defaults so ingestion never hard-fails on a single missing field.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.text import extract_hashtags
from app.utils.url_utils import detect_platform
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_html import fetch_youtube_html_metrics
from app.utils.youtube_innertube import fetch_youtube_innertube_metadata
from app.utils.youtube_social import fetch_youtube_social_metadata
from app.utils.youtube_web import YouTubeWebMetadata, fetch_youtube_web_metadata
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)


def _as_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _as_metric_int(value: Any) -> int | None:
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
    s = str(raw_date or "")
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def _metadata_is_empty(raw: RawMetadata) -> bool:
    return raw.title == "Unknown title" and raw.creator == "Unknown creator"


def _youtube_needs_views(raw: RawMetadata) -> bool:
    return raw.views == 0


def _youtube_needs_details(raw: RawMetadata) -> bool:
    return (
        _metadata_is_empty(raw)
        or raw.duration_seconds == 0
        or raw.comments is None
        or raw.upload_date is None
    )


def _merge_metadata(base: RawMetadata, patch: RawMetadata) -> RawMetadata:
    return RawMetadata(
        platform=base.platform,
        title=base.title if base.title != "Unknown title" else patch.title,
        creator=base.creator if base.creator != "Unknown creator" else patch.creator,
        creator_url=base.creator_url or patch.creator_url,
        follower_count=base.follower_count or patch.follower_count,
        thumbnail=base.thumbnail or patch.thumbnail,
        views=base.views or patch.views,
        likes=base.likes if base.likes is not None else patch.likes,
        comments=base.comments if base.comments is not None else patch.comments,
        duration_seconds=base.duration_seconds or patch.duration_seconds,
        upload_date=base.upload_date or patch.upload_date,
        hashtags=base.hashtags or patch.hashtags,
        description=base.description or patch.description,
        raw=base.raw or patch.raw,
    )


def _web_to_raw(web: YouTubeWebMetadata, platform: Platform) -> RawMetadata:
    return RawMetadata(
        platform=platform,
        title=web.title,
        creator=web.creator,
        creator_url=web.creator_url,
        thumbnail=web.thumbnail,
        views=web.views,
        likes=web.likes,
        comments=web.comments,
        duration_seconds=web.duration_seconds,
        upload_date=web.upload_date,
        description=web.description,
    )


class MetadataService:
    def fetch(self, url: str) -> RawMetadata:
        platform = detect_platform(url)
        if platform == Platform.youtube:
            return self._fetch_youtube(url)

        try:
            return self._fetch_with_ytdlp(url, platform)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Metadata extraction failed for %s: %s", url, exc)
            return RawMetadata(platform=platform)

    def _fetch_youtube(self, url: str) -> RawMetadata:
        """YouTube: layered fallbacks for cloud hosts where youtube.com is blocked."""
        result = RawMetadata(platform=Platform.youtube)
        cloud = is_youtube_cloud_host()

        from app.utils.youtube_api import fetch_youtube_api_metadata

        api_meta = fetch_youtube_api_metadata(url)
        if api_meta:
            logger.info("YouTube metadata from Data API for %s", url)
            result = _merge_metadata(result, api_meta)

        if not cloud:
            try:
                ytdlp = self._fetch_with_ytdlp(url, Platform.youtube)
                result = _merge_metadata(result, ytdlp)
            except Exception as exc:  # noqa: BLE001
                logger.warning("yt-dlp failed for %s: %s", url, exc)

        if not cloud and (_youtube_needs_views(result) or _youtube_needs_details(result)):
            innertube = fetch_youtube_innertube_metadata(url)
            if innertube:
                logger.info("YouTube metadata enriched via innertube for %s", url)
                result = _merge_metadata(result, innertube)

        if not cloud and (_youtube_needs_views(result) or _youtube_needs_details(result)):
            html_metrics = fetch_youtube_html_metrics(url)
            if html_metrics:
                logger.info("YouTube metadata enriched via HTML metrics for %s", url)
                result = _merge_metadata(result, html_metrics)

        if not cloud and (_youtube_needs_views(result) or _youtube_needs_details(result)):
            web = fetch_youtube_web_metadata(url)
            if web:
                logger.info("YouTube metadata enriched via web scrape for %s", url)
                result = _merge_metadata(result, _web_to_raw(web, Platform.youtube))

        if _youtube_needs_views(result) or result.comments is None or (
            cloud and result.duration_seconds == 0
        ):
            social = fetch_youtube_social_metadata(url)
            if social:
                logger.info("YouTube metadata enriched via social APIs for %s", url)
                result = _merge_metadata(result, social)

        if _metadata_is_empty(result):
            oembed = self._fetch_youtube_oembed(url)
            if oembed:
                logger.info("YouTube metadata recovered via oEmbed for %s", url)
                result = _merge_metadata(result, oembed)

        return result

    def _fetch_youtube_oembed(self, url: str) -> RawMetadata | None:
        try:
            oembed_url = (
                "https://www.youtube.com/oembed"
                f"?url={quote(url, safe='')}&format=json"
            )
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(
                    oembed_url,
                    headers={"User-Agent": "Vanadium/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube oEmbed fallback failed for %s: %s", url, exc)
            return None

        title = (data.get("title") or "").strip()
        if not title:
            return None

        return RawMetadata(
            platform=Platform.youtube,
            title=title,
            creator=(data.get("author_name") or "Unknown creator").strip(),
            creator_url=data.get("author_url"),
            thumbnail=data.get("thumbnail_url"),
        )

    def _fetch_with_ytdlp(self, url: str, platform: Platform) -> RawMetadata:
        from yt_dlp import YoutubeDL

        opts = base_ytdlp_opts(skip_download=True, extract_flat=False)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        info = info or {}
        description = info.get("description") or ""
        tags = info.get("tags") or []

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

        views = _as_int(info.get("view_count") or info.get("play_count"))
        likes = _as_metric_int(info.get("like_count"))
        comments = _as_metric_int(info.get("comment_count"))

        if platform == Platform.instagram and (info.get("like_count") is None or likes == 0):
            likes = None

        return RawMetadata(
            platform=platform,
            title=info.get("title") or "Unknown title",
            creator=creator,
            creator_url=_creator_profile_url(info, platform),
            follower_count=_as_int(
                info.get("channel_follower_count") or info.get("uploader_subscriber_count")
            ),
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
