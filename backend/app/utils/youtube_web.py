"""YouTube watch-page metadata extraction (secondary fallback)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging import get_logger
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

_WATCH_UA = (
    "Mozilla/5.0 (Linux; Android 10; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

_LIKE_RE = re.compile(r'"likeCount"\s*:\s*"(\d+)"')
_COMMENT_RE = re.compile(r'"commentCount"\s*:\s*"(\d+)"')

_PLAYER_MARKERS = (
    "var ytInitialPlayerResponse = ",
    "ytInitialPlayerResponse = ",
    "window['ytInitialPlayerResponse'] = ",
)


@dataclass
class YouTubeWebMetadata:
    title: str
    creator: str
    creator_url: str | None
    thumbnail: str | None
    views: int
    likes: int | None
    comments: int | None
    duration_seconds: int
    upload_date: str | None
    description: str = ""


def _parse_upload_date(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def _first_int(pattern: re.Pattern[str], html: str) -> int | None:
    match = pattern.search(html)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_json_object(html: str, marker: str) -> dict | None:
    """Extract a JSON object after ``marker`` using brace-depth counting."""
    idx = html.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    while start < len(html) and html[start] in " \t\n\r":
        start += 1
    if start >= len(html) or html[start] != "{":
        return None
    depth = 0
    for i in range(start, len(html)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _player_from_html(html: str) -> dict | None:
    for marker in _PLAYER_MARKERS:
        obj = _extract_json_object(html, marker)
        if obj:
            return obj
    return None


def fetch_youtube_web_metadata(url: str) -> YouTubeWebMetadata | None:
    """Extract metadata from the YouTube watch page HTML."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    watch_urls = [
        f"https://m.youtube.com/watch?v={video_id}",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    headers = {
        "User-Agent": _WATCH_UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    cookies = {"CONSENT": "YES+cb.20210328-17-p0.en+FX+667"}

    html = ""
    player: dict | None = None
    for watch_url in watch_urls:
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                resp = client.get(watch_url, headers=headers, cookies=cookies)
                resp.raise_for_status()
                html = resp.text
            player = _player_from_html(html)
            if player:
                break
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube web scrape failed for %s: %s", watch_url, exc)

    if not player:
        logger.warning("YouTube web scrape: no player response for %s", video_id)
        return None

    details = player.get("videoDetails") or {}
    micro = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}

    title = (details.get("title") or "").strip()
    if not title:
        return None

    channel_id = details.get("channelId")
    author = (details.get("author") or "Unknown creator").strip()
    creator_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else None

    thumbnails = details.get("thumbnail", {}).get("thumbnails") or []
    thumbnail = thumbnails[-1].get("url") if thumbnails else None
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    likes = _first_int(_LIKE_RE, html)
    if likes is None and micro.get("likeCount") is not None:
        try:
            likes = int(micro["likeCount"])
        except (TypeError, ValueError):
            likes = None

    comments = _first_int(_COMMENT_RE, html)

    return YouTubeWebMetadata(
        title=title,
        creator=author,
        creator_url=creator_url,
        thumbnail=thumbnail,
        views=int(details.get("viewCount") or 0),
        likes=likes,
        comments=comments,
        duration_seconds=int(details.get("lengthSeconds") or 0),
        upload_date=_parse_upload_date(micro.get("publishDate") or micro.get("uploadDate")),
        description=(details.get("shortDescription") or "").strip(),
    )
