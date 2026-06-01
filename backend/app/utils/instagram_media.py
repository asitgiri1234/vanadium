"""Instagram direct media URLs (audio/thumbnail) without full yt-dlp download."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.logging import get_logger
from app.utils.cookie_utils import cookie_header_for_url
from app.utils.instagram_media_api import fetch_instagram_media_info
from app.utils.instagram_page_media import extract_instagram_media_urls
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)

_CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
    "Accept": "*/*",
}


def _extract_info(url: str) -> dict[str, Any] | None:
    from yt_dlp import YoutubeDL

    try:
        opts = base_ytdlp_opts(skip_download=True)
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram media info failed for %s: %s", url, exc)
        return None


def _best_audio_url(info: dict[str, Any]) -> str | None:
    direct = info.get("url")
    if direct and str(direct).startswith("http"):
        return str(direct)

    for fmt in info.get("formats") or []:
        if fmt.get("vcodec") in ("none", None) and fmt.get("acodec") not in ("none", None):
            url = fmt.get("url")
            if url:
                return str(url)
    return None


def _best_thumbnail_url(info: dict[str, Any]) -> str | None:
    thumb = info.get("thumbnail")
    if thumb:
        return str(thumb)
    thumbs = info.get("thumbnails") or []
    if thumbs:
        return str(thumbs[-1].get("url") or "")
    return None


def _download_bytes(url: str, out_path: str, min_size: int = 1000) -> bool:
    headers = {**_CDN_HEADERS, **cookie_header_for_url(url)}
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            with open(out_path, "wb") as fh:
                fh.write(resp.content)
        return os.path.getsize(out_path) >= min_size
    except Exception as exc:  # noqa: BLE001
        logger.warning("CDN download failed for %s: %s", url[:80], exc)
        return False


def _collect_media_urls(
    url: str,
    ig_media: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    video_urls: list[str] = []
    thumb_urls: list[str] = []

    if ig_media:
        video_urls.extend(str(u) for u in ig_media.get("ig_video_urls") or [] if u)
        thumb_urls.extend(str(u) for u in ig_media.get("ig_thumbnail_urls") or [] if u)
        if ig_media.get("thumbnail_url"):
            thumb_urls.append(str(ig_media["thumbnail_url"]))

    if not video_urls:
        media_info = fetch_instagram_media_info(url)
        if media_info:
            for u in media_info.get("video_urls") or []:
                if u not in video_urls:
                    video_urls.append(str(u))

    scraped = extract_instagram_media_urls(url)
    for u in scraped.get("video_urls") or []:
        if u not in video_urls:
            video_urls.append(u)
    for u in scraped.get("thumbnail_urls") or []:
        if u not in thumb_urls:
            thumb_urls.append(u)

    return video_urls, thumb_urls


def download_instagram_audio(
    url: str,
    out_path: str,
    ig_media: dict[str, Any] | None = None,
) -> str | None:
    """Download reel audio/video for Whisper (CDN URL first, yt-dlp fallback)."""
    video_urls, _ = _collect_media_urls(url, ig_media)

    for media_url in video_urls:
        if _download_bytes(media_url, out_path, min_size=5000):
            logger.info("Instagram media downloaded via page CDN for %s", url)
            return out_path

    info = _extract_info(url)
    if info:
        audio_url = _best_audio_url(info)
        if audio_url and _download_bytes(audio_url, out_path, min_size=1000):
            logger.info("Instagram audio downloaded via yt-dlp CDN for %s", url)
            return out_path

    return None


def download_instagram_thumbnails(
    url: str,
    work_dir: str,
    max_frames: int = 3,
    ig_media: dict[str, Any] | None = None,
    fallback_thumbnail: str | None = None,
) -> list[str]:
    """Download reel thumbnail(s) for cloud visual analysis."""
    _, thumb_urls = _collect_media_urls(url, ig_media)
    if fallback_thumbnail and fallback_thumbnail not in thumb_urls:
        thumb_urls.insert(0, fallback_thumbnail)

    saved: list[str] = []
    for img_url in thumb_urls[:max_frames]:
        path = os.path.join(work_dir, f"ig_frame_{len(saved):02d}.jpg")
        if _download_bytes(img_url, path, min_size=500):
            saved.append(path)

    if saved:
        logger.info("Instagram thumbnails: %d for %s", len(saved), url)
        return saved

    info = _extract_info(url)
    if not info:
        return []

    urls: list[str] = []
    primary = _best_thumbnail_url(info)
    if primary:
        urls.append(primary)
    for entry in info.get("thumbnails") or []:
        u = entry.get("url")
        if u and u not in urls:
            urls.append(str(u))

    for img_url in urls[:max_frames]:
        path = os.path.join(work_dir, f"ig_frame_{len(saved):02d}.jpg")
        if _download_bytes(img_url, path, min_size=500):
            saved.append(path)

    if saved:
        logger.info("Instagram thumbnails (yt-dlp): %d for %s", len(saved), url)
    return saved
