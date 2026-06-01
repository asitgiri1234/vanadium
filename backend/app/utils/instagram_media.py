"""Instagram direct media URLs (audio/thumbnail) without full yt-dlp download."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.logging import get_logger
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)


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


def download_instagram_audio(url: str, out_path: str) -> str | None:
    """Download reel audio via direct CDN URL when yt-dlp full download fails."""
    info = _extract_info(url)
    if not info:
        return None

    audio_url = _best_audio_url(info)
    if not audio_url:
        return None

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(
                audio_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Vanadium/1.0)"},
            )
            resp.raise_for_status()
            with open(out_path, "wb") as fh:
                fh.write(resp.content)
        if os.path.getsize(out_path) > 1000:
            logger.info("Instagram audio downloaded via direct URL for %s", url)
            return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram direct audio download failed for %s: %s", url, exc)
    return None


def download_instagram_thumbnails(url: str, work_dir: str, max_frames: int = 3) -> list[str]:
    """Download reel thumbnail(s) for cloud visual analysis."""
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

    saved: list[str] = []
    for img_url in urls[:max_frames]:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(img_url, headers={"User-Agent": "Vanadium/1.0"})
                if resp.status_code != 200 or len(resp.content) < 500:
                    continue
                path = os.path.join(work_dir, f"ig_frame_{len(saved):02d}.jpg")
                with open(path, "wb") as fh:
                    fh.write(resp.content)
                saved.append(path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("IG thumbnail download failed: %s", exc)
    if saved:
        logger.info("Instagram thumbnails: %d for %s", len(saved), url)
    return saved
