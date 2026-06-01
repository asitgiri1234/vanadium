"""Fetch Instagram reel data via the Vercel frontend proxy."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.youtube_proxy import frontend_proxy_base

logger = get_logger(__name__)


def fetch_instagram_reel_proxy(url: str) -> dict[str, Any] | None:
    base = frontend_proxy_base()
    if not base or not url.strip():
        return None

    endpoint = f"{base}/api/instagram/reel"
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            resp = client.get(endpoint, params={"url": url.strip()})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Frontend Instagram reel proxy failed for %s: %s", url, exc)
        return None

    if not isinstance(payload, dict):
        return None
    if not payload.get("ok") and not any(
        payload.get(k) is not None
        for k in ("like_count", "comment_count", "video_urls", "title", "thumbnail_url")
    ):
        return None
    logger.info("Instagram reel proxy ok for %s", url)
    return payload


def reel_proxy_to_raw(payload: dict[str, Any]) -> RawMetadata:
    likes = payload.get("like_count")
    comments = payload.get("comment_count")
    views = payload.get("view_count")
    return RawMetadata(
        platform=Platform.instagram,
        title=str(payload.get("title") or "Instagram Reel"),
        creator=str(payload.get("creator") or "Unknown creator"),
        creator_url=payload.get("creator_url"),
        thumbnail=payload.get("thumbnail_url"),
        views=int(views) if views is not None else 0,
        likes=int(likes) if likes is not None else None,
        comments=int(comments) if comments is not None else None,
        duration_seconds=int(payload.get("duration_seconds") or 0),
    )
