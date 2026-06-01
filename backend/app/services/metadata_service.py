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
from app.utils.instagram_embed import fetch_instagram_fallback_metadata
from app.utils.instagram_profile import fetch_instagram_profile_metadata, _extract_handle
from app.utils.instagram_media_api import (
    fetch_instagram_media_info,
    media_info_to_raw,
)
from app.utils.instagram_page_media import extract_instagram_media_urls
from app.utils.instagram_reel_proxy import fetch_instagram_reel_proxy, reel_proxy_to_raw
from app.utils.instagram_proxy import fetch_instagram_profile_proxy
from app.utils.metadata_display import coalesce_count, followers_known
from app.utils.text import extract_hashtags
from app.utils.url_utils import detect_platform, extract_youtube_id
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_html import fetch_youtube_html_metrics
from app.utils.youtube_innertube import fetch_youtube_innertube_metadata
from app.utils.youtube_proxy import fetch_frontend_proxy
from app.utils.youtube_social import fetch_youtube_social_metadata
from app.utils.youtube_web import YouTubeWebMetadata, fetch_youtube_web_metadata
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)


def _as_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _as_optional_positive(value: Any) -> int | None:
    n = _as_int(value)
    return n if n > 0 else None


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
        follower_count=coalesce_count(base.follower_count, patch.follower_count),
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

        if platform == Platform.instagram:
            return self._fetch_instagram(url)

        try:
            return self._fetch_with_ytdlp(url, platform)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Metadata extraction failed for %s: %s", url, exc)
            return RawMetadata(platform=platform)

    def _fetch_youtube(self, url: str) -> RawMetadata:
        """YouTube: layered fallbacks for cloud hosts where youtube.com is blocked."""
        result = RawMetadata(platform=Platform.youtube)
        cloud = is_youtube_cloud_host()
        video_id = extract_youtube_id(url)

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

        if _youtube_needs_views(result) or _youtube_needs_details(result):
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

        if cloud and result.duration_seconds == 0 and video_id:
            scrape = fetch_frontend_proxy("scrape", video_id)
            if scrape and scrape.get("ok"):
                metrics = scrape.get("metrics") or {}
                patch = RawMetadata(
                    platform=Platform.youtube,
                    views=int(metrics.get("viewCount") or 0),
                    likes=int(metrics["likeCount"]) if metrics.get("likeCount") is not None else None,
                    comments=int(metrics["commentCount"]) if metrics.get("commentCount") is not None else None,
                    duration_seconds=int(metrics.get("lengthSeconds") or 0),
                )
                logger.info("YouTube metadata enriched via frontend scrape for %s", url)
                result = _merge_metadata(result, patch)

        if _metadata_is_empty(result):
            oembed = self._fetch_youtube_oembed(url)
            if oembed:
                logger.info("YouTube metadata recovered via oEmbed for %s", url)
                result = _merge_metadata(result, oembed)

        if not followers_known(result.follower_count):
            channel_id = self._extract_youtube_channel_id(result)
            if channel_id:
                from app.utils.youtube_api import fetch_youtube_channel_metadata

                channel_meta = fetch_youtube_channel_metadata(channel_id)
                if channel_meta:
                    result = _merge_metadata(result, channel_meta)

        if cloud and (
            result.duration_seconds == 0 or not followers_known(result.follower_count)
        ):
            proxy_meta = self._fetch_youtube_metadata_proxy(video_id)
            if proxy_meta:
                logger.info("YouTube metadata enriched via frontend Data API proxy for %s", url)
                result = _merge_metadata(result, proxy_meta)

        return result

    @staticmethod
    def _extract_youtube_channel_id(raw: RawMetadata) -> str | None:
        url = raw.creator_url or ""
        if "/channel/" in url:
            return url.split("/channel/")[-1].split("/")[0].split("?")[0]
        info = raw.raw if isinstance(raw.raw, dict) else {}
        channel_id = info.get("channel_id")
        return str(channel_id) if channel_id else None

    @staticmethod
    def _fetch_youtube_metadata_proxy(video_id: str | None) -> RawMetadata | None:
        if not video_id:
            return None
        payload = fetch_frontend_proxy("metadata", video_id)
        if not payload or not payload.get("ok"):
            return None
        meta = payload.get("metadata")
        if not isinstance(meta, dict):
            return None
        return RawMetadata(
            platform=Platform.youtube,
            title=meta.get("title") or "Unknown title",
            creator=meta.get("creator") or "Unknown creator",
            creator_url=meta.get("creator_url"),
            follower_count=_as_optional_positive(meta.get("follower_count")),
            thumbnail=meta.get("thumbnail"),
            views=int(meta.get("views") or 0),
            likes=int(meta["likes"]) if meta.get("likes") is not None else None,
            comments=int(meta["comments"]) if meta.get("comments") is not None else None,
            duration_seconds=int(meta.get("duration_seconds") or 0),
            upload_date=meta.get("upload_date"),
        )

    def _fetch_instagram(self, url: str) -> RawMetadata:
        result = RawMetadata(platform=Platform.instagram)
        media_hints: dict[str, Any] = {}

        # Authenticated media API — most reliable source for likes/comments + video CDN.
        media_info = fetch_instagram_media_info(url)
        if media_info:
            result = _merge_metadata(result, media_info_to_raw(media_info))
            if media_info.get("video_urls"):
                media_hints["ig_video_urls"] = list(media_info["video_urls"])
            if media_info.get("thumbnail_urls"):
                media_hints["ig_thumbnail_urls"] = list(media_info["thumbnail_urls"])
            if media_info.get("thumbnail_url"):
                media_hints["thumbnail_url"] = media_info["thumbnail_url"]

        if is_youtube_cloud_host():
            proxy = fetch_instagram_reel_proxy(url)
            if proxy:
                result = _merge_metadata(result, reel_proxy_to_raw(proxy))
                if proxy.get("video_urls"):
                    media_hints["ig_video_urls"] = proxy.get("video_urls")
                if proxy.get("thumbnail_urls"):
                    media_hints["ig_thumbnail_urls"] = proxy.get("thumbnail_urls")
                if proxy.get("thumbnail_url"):
                    media_hints["thumbnail_url"] = proxy.get("thumbnail_url")

        try:
            ytdlp = self._fetch_with_ytdlp(url, Platform.instagram)
            result = _merge_metadata(result, ytdlp)
            if isinstance(ytdlp.raw, dict):
                media_hints.update(ytdlp.raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Instagram yt-dlp failed for %s: %s", url, exc)

        if result.title == "Unknown title" or not result.thumbnail:
            fallback = fetch_instagram_fallback_metadata(url)
            if fallback:
                result = _merge_metadata(result, fallback)
                if fallback.thumbnail:
                    media_hints["thumbnail_url"] = fallback.thumbnail

        scraped = extract_instagram_media_urls(url)
        if scraped.get("video_urls"):
            media_hints.setdefault("ig_video_urls", [])
            for u in scraped["video_urls"]:
                if u not in media_hints["ig_video_urls"]:
                    media_hints["ig_video_urls"].append(u)
        if scraped.get("thumbnail_urls"):
            media_hints.setdefault("ig_thumbnail_urls", [])
            for u in scraped["thumbnail_urls"]:
                if u not in media_hints["ig_thumbnail_urls"]:
                    media_hints["ig_thumbnail_urls"].append(u)

        engagement = RawMetadata(platform=Platform.instagram)
        if scraped.get("like_count") is not None:
            engagement.likes = int(scraped["like_count"])
        if scraped.get("comment_count") is not None:
            engagement.comments = int(scraped["comment_count"])
        if scraped.get("view_count") is not None:
            engagement.views = int(scraped["view_count"])
        if scraped.get("duration_seconds") is not None:
            engagement.duration_seconds = int(scraped["duration_seconds"])
        if (
            engagement.likes is not None
            or engagement.comments is not None
            or engagement.views
            or engagement.duration_seconds
        ):
            result = _merge_metadata(result, engagement)

        result.raw = {
            **(result.raw if isinstance(result.raw, dict) else {}),
            **media_hints,
        }

        if not followers_known(result.follower_count):
            raw_info = result.raw if isinstance(result.raw, dict) else None
            handle = _extract_handle(
                result.creator_url,
                raw_info.get("uploader_id") if raw_info else None,
            )
            if not handle and raw_info:
                handle = _extract_handle(
                    raw_info.get("uploader_url") or raw_info.get("channel_url"),
                    raw_info.get("uploader_id") or raw_info.get("channel"),
                )

            profile = None
            if is_youtube_cloud_host() and handle:
                profile = fetch_instagram_profile_proxy(handle)

            if not profile:
                profile = fetch_instagram_profile_metadata(
                    result.creator_url,
                    raw_info.get("uploader_id") if raw_info else None,
                    raw_info,
                )
            if profile:
                result = _merge_metadata(result, profile)

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

        if platform == Platform.instagram and info.get("like_count") is None:
            likes = None

        return RawMetadata(
            platform=platform,
            title=info.get("title") or "Unknown title",
            creator=creator,
            creator_url=_creator_profile_url(info, platform),
            follower_count=_as_optional_positive(
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
