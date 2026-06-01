"""Instagram /api/v1/media/{pk}/info/ — likes, comments, and CDN video URLs."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.cookie_utils import cookie_header_for_url
from app.utils.instagram_shortcode import shortcode_to_media_pk
from app.utils.url_utils import extract_instagram_shortcode
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_proxy import frontend_proxy_base

logger = get_logger(__name__)

_IG_APP_ID = "936619743392459"
_IG_ORIGIN = "https://www.instagram.com"


def _api_headers(referer: str) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "x-ig-app-id": _IG_APP_ID,
        "Accept": "*/*",
        "x-requested-with": "XMLHttpRequest",
        "Referer": referer,
        **cookie_header_for_url(_IG_ORIGIN),
    }
    cookie = headers.get("Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("csrftoken="):
            headers["x-csrftoken"] = part.split("=", 1)[1]
            break
    return headers


def _parse_media_item(item: dict[str, Any]) -> dict[str, Any]:
    likes = item.get("like_count")
    if likes is None:
        edge = item.get("edge_media_preview_like") or {}
        if isinstance(edge, dict):
            likes = edge.get("count")

    comments = item.get("comment_count")
    if comments is None:
        edge = item.get("edge_media_to_parent_comment") or item.get("edge_media_to_comment") or {}
        if isinstance(edge, dict):
            comments = edge.get("count")

    views = item.get("play_count") or item.get("view_count") or item.get("video_view_count")

    video_urls: list[str] = []
    for version in item.get("video_versions") or []:
        if isinstance(version, dict) and version.get("url"):
            url = str(version["url"])
            if url.startswith("http") and url not in video_urls:
                video_urls.append(url)

    thumb_urls: list[str] = []
    candidates = item.get("image_versions2") or {}
    if isinstance(candidates, dict):
        for cand in candidates.get("candidates") or []:
            if isinstance(cand, dict) and cand.get("url"):
                url = str(cand["url"])
                if url.startswith("http") and url not in thumb_urls:
                    thumb_urls.append(url)

    duration = item.get("video_duration")
    if duration is not None:
        try:
            duration = int(float(duration))
        except (TypeError, ValueError):
            duration = None

    user = item.get("user") or {}
    creator = user.get("full_name") or user.get("username") if isinstance(user, dict) else None
    username = user.get("username") if isinstance(user, dict) else None

    caption = item.get("caption") or {}
    title = None
    if isinstance(caption, dict):
        title = (caption.get("text") or "").strip()[:300]

    return {
        "like_count": int(likes) if likes is not None else None,
        "comment_count": int(comments) if comments is not None else None,
        "view_count": int(views) if views is not None else None,
        "duration_seconds": duration,
        "video_urls": video_urls,
        "thumbnail_urls": thumb_urls,
        "title": title,
        "creator": creator or username,
        "creator_url": f"https://www.instagram.com/{username}/" if username else None,
        "thumbnail_url": thumb_urls[0] if thumb_urls else None,
    }


def fetch_instagram_media_info_direct(reel_url: str) -> dict[str, Any] | None:
    """Call Instagram media info API from this host (needs session cookies)."""
    shortcode = extract_instagram_shortcode(reel_url)
    if not shortcode:
        return None
    media_pk = shortcode_to_media_pk(shortcode)
    if not media_pk:
        return None

    clean_url = reel_url.split("?")[0].rstrip("/")
    api_url = f"{_IG_ORIGIN}/api/v1/media/{media_pk}/info/"
    headers = _api_headers(clean_url)

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(api_url, headers=headers)
            if resp.status_code != 200:
                logger.debug(
                    "Instagram media info HTTP %s for %s",
                    resp.status_code,
                    shortcode,
                )
                return None
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Instagram media info failed for %s: %s", shortcode, exc)
        return None

    items = data.get("items") if isinstance(data, dict) else None
    if not items or not isinstance(items, list):
        return None

    parsed = _parse_media_item(items[0])
    if not any(
        parsed.get(k)
        for k in ("like_count", "comment_count", "view_count", "video_urls")
    ):
        return None

    logger.info(
        "Instagram media API: likes=%s comments=%s videos=%d for %s",
        parsed.get("like_count"),
        parsed.get("comment_count"),
        len(parsed.get("video_urls") or []),
        shortcode,
    )
    return parsed


def fetch_instagram_media_info_proxy(reel_url: str) -> dict[str, Any] | None:
    """Fetch media info via Vercel (non-datacenter IP + optional cookie env)."""
    base = frontend_proxy_base()
    if not base:
        return None
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            resp = client.get(
                f"{base}/api/instagram/media",
                params={"url": reel_url.strip()},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram media proxy failed for %s: %s", reel_url, exc)
        return None

    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    return payload


def fetch_instagram_media_info(reel_url: str) -> dict[str, Any] | None:
    """Best-effort media info: direct (cookies) then Vercel proxy on cloud."""
    info = fetch_instagram_media_info_direct(reel_url)
    if info:
        return info
    if is_youtube_cloud_host():
        return fetch_instagram_media_info_proxy(reel_url)
    return None


def media_info_to_raw(info: dict[str, Any]) -> RawMetadata:
    likes = info.get("like_count")
    comments = info.get("comment_count")
    views = info.get("view_count")
    return RawMetadata(
        platform=Platform.instagram,
        title=str(info.get("title") or "Instagram Reel"),
        creator=str(info.get("creator") or "Unknown creator"),
        creator_url=info.get("creator_url"),
        thumbnail=info.get("thumbnail_url"),
        views=int(views) if views is not None else 0,
        likes=int(likes) if likes is not None else None,
        comments=int(comments) if comments is not None else None,
        duration_seconds=int(info.get("duration_seconds") or 0),
    )
