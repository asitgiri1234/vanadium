"""Download YouTube audio via Innertube streamingData (works when yt-dlp is blocked)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.logging import get_logger
from app.utils.url_utils import extract_youtube_id
from app.utils.youtube_captions import _INNERTUBE_CLIENTS, _INNERTUBE_KEY, _WATCH_UA

logger = get_logger(__name__)

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": _WATCH_UA,
    "Origin": "https://www.youtube.com",
    "Referer": "https://www.youtube.com/",
}


def _best_audio_url(player: dict[str, Any]) -> str | None:
    streaming = player.get("streamingData") or {}
    candidates: list[tuple[int, str]] = []

    for fmt in streaming.get("adaptiveFormats") or []:
        if not isinstance(fmt, dict):
            continue
        mime = str(fmt.get("mimeType") or "")
        url = fmt.get("url")
        if not url or "audio" not in mime:
            continue
        bitrate = int(fmt.get("bitrate") or fmt.get("averageBitrate") or 0)
        candidates.append((bitrate, str(url)))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    for fmt in streaming.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        url = fmt.get("url")
        if url:
            return str(url)
    return None


def fetch_innertube_player(video_id: str) -> dict[str, Any] | None:
    for client in _INNERTUBE_CLIENTS:
        try:
            with httpx.Client(timeout=35.0, follow_redirects=True) as http:
                resp = http.post(
                    f"https://youtubei.googleapis.com/youtubei/v1/player?key={_INNERTUBE_KEY}",
                    json={"context": {"client": client}, "videoId": video_id},
                    headers=_HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Innertube player %s failed: %s", client.get("clientName"), exc)
    return None


def download_youtube_audio_innertube(url: str, out_path: str) -> str | None:
    """Download audio using Innertube adaptiveFormats CDN URL."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    player = fetch_innertube_player(video_id)
    if not player:
        return None

    audio_url = _best_audio_url(player)
    if not audio_url:
        return None

    try:
        with httpx.Client(timeout=180.0, follow_redirects=True) as client:
            resp = client.get(
                audio_url,
                headers={"User-Agent": _WATCH_UA, "Referer": "https://www.youtube.com/"},
            )
            resp.raise_for_status()
            with open(out_path, "wb") as fh:
                fh.write(resp.content)
        if os.path.getsize(out_path) > 1000:
            logger.info("YouTube audio downloaded via innertube for %s", video_id)
            return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Innertube audio download failed for %s: %s", video_id, exc)
    return None
