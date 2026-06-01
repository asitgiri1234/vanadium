"""Instagram profile enrichment (follower count, creator details)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)

_IG_APP_ID = "936619743392459"


def _extract_handle(creator_url: str | None, uploader_id: str | None) -> str | None:
    if uploader_id:
        clean = str(uploader_id).lstrip("@").strip()
        if clean:
            return clean

    if not creator_url:
        return None

    path = urlparse(creator_url).path.strip("/")
    if not path:
        return None
    handle = path.split("/")[0]
    if handle in {"p", "reel", "reels", "stories", "tv"}:
        return None
    return handle


def _followers_from_ytdlp_profile(handle: str) -> int | None:
    from yt_dlp import YoutubeDL

    profile_url = f"https://www.instagram.com/{handle}/"
    opts = base_ytdlp_opts(skip_download=True, extract_flat=False)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile_url, download=False) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram profile yt-dlp failed for @%s: %s", handle, exc)
        return None

    for key in (
        "channel_follower_count",
        "follower_count",
        "followers_count",
        "subscriber_count",
    ):
        val = info.get(key)
        if val is not None:
            try:
                count = int(val)
                if count > 0:
                    return count
            except (TypeError, ValueError):
                continue
    return None


def _followers_from_web_profile(handle: str) -> int | None:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(
                "https://www.instagram.com/api/v1/users/web_profile_info/",
                params={"username": handle},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "x-ig-app-id": _IG_APP_ID,
                    "Accept": "*/*",
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram web_profile_info failed for @%s: %s", handle, exc)
        return None

    user = (data.get("data") or {}).get("user") or {}
    count = (user.get("edge_followed_by") or {}).get("count")
    if count is not None:
        try:
            return int(count)
        except (TypeError, ValueError):
            return None
    return None


def _followers_from_profile_html(handle: str) -> int | None:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(
                f"https://www.instagram.com/{handle}/",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram profile HTML failed for @%s: %s", handle, exc)
        return None

    for pattern in (
        r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)',
        r'"follower_count"\s*:\s*(\d+)',
        r'"followers"\s*:\s*(\d+)',
    ):
        match = re.search(pattern, html)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def fetch_instagram_profile_metadata(
    creator_url: str | None,
    uploader_id: str | None,
    raw_info: dict[str, Any] | None = None,
) -> RawMetadata | None:
    """Best-effort follower count + creator details for Instagram."""
    handle = _extract_handle(creator_url, uploader_id)
    if not handle and raw_info:
        handle = _extract_handle(
            raw_info.get("uploader_url") or raw_info.get("channel_url"),
            raw_info.get("uploader_id") or raw_info.get("channel"),
        )
    if not handle:
        return None

    followers: int | None = None
    for fetcher in (
        _followers_from_ytdlp_profile,
        _followers_from_web_profile,
        _followers_from_profile_html,
    ):
        followers = fetcher(handle)
        if followers and followers > 0:
            logger.info(
                "Instagram followers for @%s: %s via %s",
                handle,
                followers,
                fetcher.__name__,
            )
            break

    if not followers:
        return None

    creator_url = creator_url or f"https://www.instagram.com/{handle}/"
    creator_name = handle
    if raw_info:
        creator_name = (
            raw_info.get("uploader")
            or raw_info.get("channel")
            or raw_info.get("creator")
            or handle
        )

    return RawMetadata(
        platform=Platform.instagram,
        creator=str(creator_name),
        creator_url=creator_url,
        follower_count=followers,
    )
