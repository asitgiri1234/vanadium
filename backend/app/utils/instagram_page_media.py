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
_VIDEO_DURATION_RE = re.compile(r'"video_duration"\s*:\s*([\d.]+)')
_LIKE_COUNT_RE = re.compile(r'"like_count"\s*:\s*(\d+)')
_COMMENT_COUNT_RE = re.compile(r'"comment_count"\s*:\s*(\d+)')
_PLAY_COUNT_RE = re.compile(r'"play_count"\s*:\s*(\d+)')
_EDGE_LIKE_RE = re.compile(
    r'"edge_media_preview_like"\s*:\s*\{\s*"count"\s*:\s*(\d+)'
)
_EDGE_COMMENT_RE = re.compile(
    r'"edge_media_to_(?:parent_)?comment"\s*:\s*\{\s*"count"\s*:\s*(\d+)'
)
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


def _first_int(patterns: list[re.Pattern[str]], html: str) -> int | None:
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            return int(match.group(1))
    return None


def extract_instagram_engagement(html: str) -> dict[str, int | None]:
    """Parse likes/comments/views from embed or watch page JSON blobs."""
    likes = _first_int([_LIKE_COUNT_RE, _EDGE_LIKE_RE], html)
    comments = _first_int([_COMMENT_COUNT_RE, _EDGE_COMMENT_RE], html)
    views = _first_int([_PLAY_COUNT_RE], html)
    duration: int | None = None
    dur_match = _VIDEO_DURATION_RE.search(html)
    if dur_match:
        duration = int(float(dur_match.group(1)))
    return {
        "like_count": likes,
        "comment_count": comments,
        "view_count": views,
        "duration_seconds": duration,
    }


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
    engagement: dict[str, int | None] = {
        "like_count": None,
        "comment_count": None,
        "view_count": None,
        "duration_seconds": None,
    }

    for page_url in (embed_url, f"{reel_url}/embed/", reel_url):
        html = _fetch_html(page_url)
        if not html:
            continue
        video_urls.extend(
            _unique_urls([_VIDEO_URL_RE, _PLAYBACK_RE, _CONTENT_URL_RE], html)
        )
        thumb_urls.extend(_unique_urls([_THUMB_RE], html))
        page_eng = extract_instagram_engagement(html)
        for key, value in page_eng.items():
            if value is not None and engagement.get(key) is None:
                engagement[key] = value
        if video_urls:
            break

    return {
        "video_urls": list(dict.fromkeys(video_urls)),
        "thumbnail_urls": list(dict.fromkeys(thumb_urls)),
        **engagement,
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
