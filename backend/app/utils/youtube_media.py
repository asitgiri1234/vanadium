"""YouTube direct audio URL download (Whisper fallback when captions fail)."""

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
        logger.warning("YouTube audio info failed for %s: %s", url, exc)
        return None


def _best_audio_url(info: dict[str, Any]) -> str | None:
    for fmt in info.get("formats") or []:
        if fmt.get("vcodec") in ("none", None) and fmt.get("acodec") not in ("none", None):
            url = fmt.get("url")
            if url:
                return str(url)
    direct = info.get("url")
    if direct and str(direct).startswith("http"):
        return str(direct)
    return None


def download_youtube_audio(url: str, out_path: str) -> str | None:
    """Download audio via CDN URL when full yt-dlp download is blocked."""
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
            logger.info("YouTube audio downloaded via direct URL for %s", url)
            return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube direct audio download failed for %s: %s", url, exc)
    return None
