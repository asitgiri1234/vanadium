"""Fetch Instagram profile data via the Vercel frontend proxy."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.youtube_proxy import frontend_proxy_base

logger = get_logger(__name__)


def fetch_instagram_profile_proxy(handle: str) -> RawMetadata | None:
    """Follower count from Vercel (non-datacenter IP) when Render is blocked."""
    base = frontend_proxy_base()
    clean = handle.lstrip("@").strip()
    if not base or not clean:
        return None

    url = f"{base}/api/instagram/profile"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url, params={"handle": clean})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Frontend Instagram profile proxy failed for @%s: %s", clean, exc)
        return None

    if not isinstance(payload, dict) or not payload.get("ok"):
        return None

    followers = payload.get("follower_count")
    try:
        count = int(followers) if followers is not None else 0
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None

    logger.info("Instagram profile proxy ok for @%s: %s followers", clean, count)
    return RawMetadata(
        platform=Platform.instagram,
        creator=clean,
        creator_url=str(payload.get("creator_url") or f"https://www.instagram.com/{clean}/"),
        follower_count=count,
    )
