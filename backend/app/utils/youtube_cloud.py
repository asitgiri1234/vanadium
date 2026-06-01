"""Detect cloud/datacenter hosts where youtube.com is often blocked."""

from __future__ import annotations

import os


def is_youtube_cloud_host() -> bool:
    """True on Render, Fly.io, Railway, etc."""
    if os.environ.get("YOUTUBE_CLOUD_MODE", "").lower() in ("1", "true", "yes"):
        return True
    return any(
        os.environ.get(key)
        for key in ("RENDER", "FLY_APP_NAME", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")
    )
