"""Detect chat messages that are not about the current video comparison."""

from __future__ import annotations

import re

_GREETINGS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "hiya",
        "yo",
        "sup",
        "thanks",
        "thank you",
        "thx",
        "ok",
        "okay",
        "k",
        "cool",
        "nice",
        "great",
        "good morning",
        "good night",
        "gm",
        "gn",
    }
)

_TOPIC_KEYWORDS = (
    "video",
    "reel",
    "hook",
    "hooks",
    "cta",
    "call to action",
    "transcript",
    "caption",
    "views",
    "view",
    "likes",
    "like",
    "comments",
    "comment",
    "engagement",
    "compare",
    "comparison",
    "instagram",
    "youtube",
    "creator",
    "content",
    "pacing",
    "thumbnail",
    "visual",
    "frame",
    "opening",
    "intro",
    "first",
    "seconds",
    "second",
    "performance",
    "audience",
    "follower",
    "script",
    "narrative",
    "story",
    "retention",
    "watch",
    "outperform",
    "winner",
    "video a",
    "video b",
    "vid a",
    "vid b",
)


def is_off_topic_message(message: str) -> bool:
    """True when the message is unlikely to be about the A/B video comparison."""
    text = re.sub(r"\s+", " ", message.strip().lower())
    if not text:
        return True

    bare = text.rstrip("!?.…")
    if bare in _GREETINGS:
        return True

    if any(kw in text for kw in _TOPIC_KEYWORDS):
        return False

    # Very short messages without comparison keywords are usually small talk.
    if len(text.split()) <= 5:
        return True

    return False


OFF_TOPIC_REPLY = (
    "That isn't really about these two videos, so I don't have much to add on that. "
    "Ask me about hooks, pacing, CTAs, engagement, transcripts, or why one video "
    "outperformed the other — I'm here for that."
)
