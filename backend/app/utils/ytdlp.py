"""Shared yt-dlp option helpers.

Centralises authentication (cookies) so metadata extraction and Instagram audio
download stay in sync. Instagram only exposes view/play counts on its
authenticated API path, which yt-dlp reaches when given valid session cookies.
"""

from __future__ import annotations

import os

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
