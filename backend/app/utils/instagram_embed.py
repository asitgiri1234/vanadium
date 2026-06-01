"""Instagram embed / oEmbed fallbacks when yt-dlp fails."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.cookie_utils import cookie_header_for_url
from app.utils.instagram_profile import _extract_handle

logger = get_logger(__name__)

_IG_APP_ID = "936619743392459"
_OG_TAG = re.compile(
    r'<meta\s+(?:property|name)=["\'](og:[^"\']+)["\']\s+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)


def _parse_og_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for match in _OG_TAG.finditer(html):
        tags[match.group(1).lower()] = match.group(2)
    return tags


def fetch_instagram_oembed(url: str) -> RawMetadata | None:
    """Public oEmbed JSON (works for some reels without login)."""
    api_url = f"https://www.instagram.com/api/v1/oembed/?url={quote(url, safe='')}"
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
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram oEmbed failed for %s: %s", url, exc)
        return None

    if not isinstance(data, dict) or not data.get("title"):
        return None

    author = (data.get("author_name") or "Unknown creator").strip()
    author_url = data.get("author_url")
    handle = _extract_handle(author_url, author.lstrip("@"))

    return RawMetadata(
        platform=Platform.instagram,
        title=(data.get("title") or "Instagram Reel").strip(),
        creator=author,
        creator_url=author_url or (f"https://www.instagram.com/{handle}/" if handle else None),
        thumbnail=data.get("thumbnail_url"),
    )


def fetch_instagram_embed_page(url: str) -> RawMetadata | None:
    """Scrape og: tags from /embed/ page (often works with session cookies)."""
    embed_url = url.rstrip("/") + "/embed/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        **cookie_header_for_url(embed_url),
    }
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(embed_url, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram embed page failed for %s: %s", url, exc)
        return None

    og = _parse_og_tags(html)
    title = og.get("og:title") or og.get("og:description")
    thumbnail = og.get("og:image")
    author_url = og.get("og:url")

    if not title and not thumbnail:
        return None

    creator = "Unknown creator"
    if title and " on Instagram:" in title:
        creator = title.split(" on Instagram:")[0].strip().strip('"')
        title = title.split(":", 1)[-1].strip().strip('"') or "Instagram Reel"

    handle = _extract_handle(author_url, creator.lstrip("@"))

    return RawMetadata(
        platform=Platform.instagram,
        title=title or "Instagram Reel",
        creator=creator,
        creator_url=author_url or (f"https://www.instagram.com/{handle}/" if handle else None),
        thumbnail=thumbnail,
    )


def fetch_instagram_json_ld(url: str) -> RawMetadata | None:
    """Parse JSON-LD from reel watch page when available."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        **cookie_header_for_url(url),
    }
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram page fetch failed for %s: %s", url, exc)
        return None

    match = re.search(
        r'<script type="application/ld\+json">(\{.*?\})</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    author = data.get("author") or {}
    creator = author.get("name") if isinstance(author, dict) else None
    creator_url = author.get("url") if isinstance(author, dict) else None

    likes: int | None = None
    comments: int | None = None
    for stat in data.get("interactionStatistic") or []:
        if not isinstance(stat, dict):
            continue
        itype = str(stat.get("interactionType") or "")
        count = stat.get("userInteractionCount")
        if count is None:
            continue
        try:
            n = int(count)
        except (TypeError, ValueError):
            continue
        if "LikeAction" in itype:
            likes = n
        elif "CommentAction" in itype:
            comments = n

    return RawMetadata(
        platform=Platform.instagram,
        title=(data.get("caption") or data.get("description") or "Instagram Reel")[:200],
        creator=creator or "Unknown creator",
        creator_url=creator_url,
        thumbnail=data.get("thumbnailUrl"),
        likes=likes,
        comments=comments,
    )


def fetch_instagram_fallback_metadata(url: str) -> RawMetadata | None:
    """Layered IG metadata when yt-dlp fails entirely."""
    for fetcher in (
        fetch_instagram_oembed,
        fetch_instagram_embed_page,
        fetch_instagram_json_ld,
    ):
        meta = fetcher(url)
        if meta and meta.title != "Unknown title":
            logger.info("Instagram fallback metadata via %s for %s", fetcher.__name__, url)
            return meta
    return None
