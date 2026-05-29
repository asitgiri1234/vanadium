"""URL parsing helpers: detect platform and extract canonical video ids."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from app.models.schemas import Platform

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}


def detect_platform(url: str) -> Platform:
    host = (urlparse(url).hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        return Platform.youtube
    if host in _INSTAGRAM_HOSTS:
        return Platform.instagram
    return Platform.unknown


def extract_youtube_id(url: str) -> str | None:
    """Return the 11-char YouTube video id from any common URL shape."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate or None

    if "youtube" in host:
        # /watch?v=ID
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            return qs["v"][0]
        # /shorts/ID , /embed/ID , /v/ID
        match = re.search(r"/(?:shorts|embed|v)/([A-Za-z0-9_-]{6,})", parsed.path)
        if match:
            return match.group(1)
    return None


def extract_instagram_shortcode(url: str) -> str | None:
    """Return the shortcode for an Instagram reel/post URL."""
    match = re.search(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", urlparse(url).path)
    return match.group(1) if match else None


def is_supported(url: str) -> bool:
    return detect_platform(url) in (Platform.youtube, Platform.instagram)
