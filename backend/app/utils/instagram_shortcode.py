"""Instagram shortcode ↔ media primary-key conversion."""

from __future__ import annotations

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def shortcode_to_media_pk(shortcode: str) -> str | None:
    """Convert reel/post shortcode to numeric media id for /api/v1/media/{id}/info/."""
    shortcode = shortcode.strip()
    if not shortcode:
        return None
    try:
        pk = 0
        for char in shortcode:
            pk = pk * 64 + _ALPHABET.index(char)
        return str(pk)
    except ValueError:
        return None
