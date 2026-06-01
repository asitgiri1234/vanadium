"""Fetch YouTube data via the Vercel frontend proxy (non-datacenter IP)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.youtube_cloud import is_youtube_cloud_host

logger = get_logger(__name__)


def frontend_proxy_base() -> str:
    explicit = settings.frontend_proxy_url.strip()
    if explicit:
        return explicit.rstrip("/")
    for origin in settings.cors_origin_list:
        if origin.startswith("https://") and "localhost" not in origin:
            return origin.rstrip("/")
    # Production fallback when CORS_ORIGINS / FRONTEND_PROXY_URL are unset on Render.
    if is_youtube_cloud_host():
        return "https://vanadium-delta.vercel.app"
    return ""


def fetch_frontend_proxy(path: str, video_id: str) -> dict[str, Any] | None:
    base = frontend_proxy_base()
    if not base or not video_id:
        return None

    url = f"{base}/api/youtube/{path}"
    try:
        with httpx.Client(timeout=90.0, follow_redirects=True) as client:
            resp = client.get(url, params={"videoId": video_id})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Frontend YouTube proxy %s failed for %s: %s", path, video_id, exc)
        return None

    if not isinstance(payload, dict):
        return None
    logger.info("Frontend YouTube proxy %s ok for %s", path, video_id)
    return payload
