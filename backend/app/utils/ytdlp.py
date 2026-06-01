"""Shared yt-dlp option helpers.

Centralises authentication (cookies) and YouTube client rotation so metadata
extraction, audio download, and visual sampling stay in sync. Instagram only
exposes view/play counts on its authenticated API path, which yt-dlp reaches
when given valid session cookies.
"""

from __future__ import annotations

import os
import shutil

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def apply_cookie_options(opts: dict) -> dict:
    """Mutate and return ``opts`` with cookie settings, if configured.

    Precedence: an explicit cookies file wins over reading from a browser.
    """
    cookie_file = settings.instagram_cookies_file.strip()
    if cookie_file:
        if os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
            logger.info("yt-dlp: using cookies file %s", cookie_file)
            return opts
        logger.warning("yt-dlp: cookies file not found: %s", cookie_file)

    browser = settings.cookies_from_browser.strip().lower()
    if browser:
        # yt-dlp expects a tuple: (browser, profile, keyring, container)
        opts["cookiesfrombrowser"] = (browser,)
        logger.info("yt-dlp: reading cookies from browser '%s'", browser)

    return opts


def base_ytdlp_opts(**extra: object) -> dict:
    """Default yt-dlp options for cloud hosts (Render/Railway) and local dev."""
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # Datacenter IPs often get bot-blocked on the default web client alone.
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "tv_downgraded", "web"],
            }
        },
    }

    if shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
        opts["remote_components"] = ["ejs:github"]

    opts.update(extra)
    return apply_cookie_options(opts)
