"""Text cleaning and timestamp formatting helpers."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")
# Transcript artefacts like [Music], [Applause], (laughs)
_BRACKET_NOISE_RE = re.compile(r"\[[^\]]*\]|\([^)]*\)")

# Common call-to-action signals used by the intelligence layer.
_CTA_PATTERNS = [
    r"\bsubscribe\b",
    r"\blike (this|the) (video|reel)\b",
    r"\bsmash (the )?like\b",
    r"\bcomment below\b",
    r"\blink in (the )?bio\b",
    r"\bcheck out\b",
    r"\bfollow (me|us|for)\b",
    r"\bsign up\b",
    r"\bturn on notifications\b",
    r"\bshare (this|with)\b",
    r"\bswipe up\b",
    r"\bdm me\b",
]
_CTA_RE = re.compile("|".join(_CTA_PATTERNS), re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise whitespace and strip bracketed transcript noise."""
    text = _BRACKET_NOISE_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def extract_hashtags(text: str) -> list[str]:
    """Return unique ``#tags`` (order-preserving) from arbitrary text."""
    seen: dict[str, None] = {}
    for tag in _HASHTAG_RE.findall(text or ""):
        seen.setdefault(f"#{tag}", None)
    return list(seen.keys())


def has_cta(text: str) -> bool:
    return bool(_CTA_RE.search(text or ""))


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``MM:SS`` (or ``HH:MM:SS`` past an hour)."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def timestamp_range(start: float, end: float) -> str:
    return f"{format_timestamp(start)}-{format_timestamp(end)}"


def first_n_seconds_text(segments: list[tuple[str, float]], n: float = 5.0) -> str:
    """Join transcript text whose start time falls within the first ``n`` seconds."""
    parts = [text for text, start in segments if start <= n]
    return clean_text(" ".join(parts)) if parts else ""


def keywords(text: str, top: int = 12) -> list[str]:
    """Naive keyword extraction: most frequent non-stopword tokens."""
    tokens = re.findall(r"[a-zA-Z']{3,}", (text or "").lower())
    counts: dict[str, int] = {}
    for tok in tokens:
        if tok in _STOPWORDS:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top]]


_STOPWORDS = {
    "the", "and", "you", "that", "this", "for", "are", "with", "your", "have",
    "but", "not", "they", "from", "what", "all", "can", "was", "out", "get",
    "his", "her", "she", "him", "our", "their", "them", "then", "than", "just",
    "like", "really", "going", "gonna", "want", "know", "yeah", "okay", "one",
    "about", "there", "here", "when", "how", "why", "who", "will", "would",
    "could", "should", "been", "more", "some", "into", "make", "made",
}
