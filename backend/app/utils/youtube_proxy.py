"""Fetch YouTube data via the Vercel frontend proxy (non-datacenter IP)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def frontend_proxy_base() -> str:
    explicit = settings.frontend_proxy_url.strip()
    if explicit:
        return explicit.rstrip("/")
    for origin in settings.cors_origin_list:
        if origin.startswith("https://") and "localhost" not in origin:
            return origin.rstrip("/")
    return ""


def fetch_frontend_proxy(path: str, video_id: str) -> dict[str, Any] | None:
    base = frontend_proxy_base()
    if not base or not video_id:
        return None

    url = f"{base}/api/youtube/{path}"
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
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
