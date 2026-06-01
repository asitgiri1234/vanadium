"""Scrape Instagram reel media URLs from embed/watch pages (no yt-dlp download)."""

from __future__ import annotations

import codecs
import json
import re
from typing import Any

import httpx

from app.core.logging import get_logger
from app.utils.cookie_utils import cookie_header_for_url

logger = get_logger(__name__)

_IG_APP_ID = "936619743392459"
_VIDEO_URL_RE = re.compile(r'"video_url"\s*:\s*"([^"]+)"')
_PLAYBACK_RE = re.compile(r'"playback_url"\s*:\s*"([^"]+)"')
_CONTENT_URL_RE = re.compile(r'"contentUrl"\s*:\s*"([^"]+)"')
_THUMB_RE = re.compile(r'"display_url"\s*:\s*"([^"]+)"')


def _decode_url(raw: str) -> str:
    cleaned = raw.replace("\\/", "/")
    if "\\u" in cleaned:
        try:
            cleaned = codecs.decode(cleaned, "unicode_escape")
        except Exception:  # noqa: BLE001
            pass
    return cleaned.strip()


def _unique_urls(patterns: list[re.Pattern[str]], html: str) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(html):
            url = _decode_url(match.group(1))
            if url.startswith("http") and url not in found:
                found.append(url)
    return found


def _fetch_html(url: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        **cookie_header_for_url(url),
    }
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram HTML fetch failed for %s: %s", url, exc)
        return None


def extract_instagram_media_urls(reel_url: str) -> dict[str, Any]:
    """Best-effort video/thumbnail CDN URLs from embed + watch pages."""
    reel_url = reel_url.split("?")[0].rstrip("/")
    embed_url = f"{reel_url}/embed/captioned/"

    video_urls: list[str] = []
    thumb_urls: list[str] = []

    for page_url in (embed_url, f"{reel_url}/embed/", reel_url):
        html = _fetch_html(page_url)
        if not html:
            continue
        video_urls.extend(
            _unique_urls([_VIDEO_URL_RE, _PLAYBACK_RE, _CONTENT_URL_RE], html)
        )
        thumb_urls.extend(_unique_urls([_THUMB_RE], html))
        if video_urls:
            break

    return {
        "video_urls": list(dict.fromkeys(video_urls)),
        "thumbnail_urls": list(dict.fromkeys(thumb_urls)),
    }


def fetch_instagram_oembed_json(reel_url: str) -> dict[str, Any] | None:
    api_url = f"https://www.instagram.com/api/v1/oembed/?url={reel_url}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "x-ig-app-id": _IG_APP_ID,
        "Accept": "application/json",
        **cookie_header_for_url("https://www.instagram.com/"),
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(api_url, headers=headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram oEmbed JSON failed: %s", exc)
        return None
