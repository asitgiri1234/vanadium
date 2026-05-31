"""Performance ranking: winner by views (when both known), else likes."""

from __future__ import annotations

from app.models.schemas import VideoMetadata, VideoSlot


def determine_winner(a: VideoMetadata, b: VideoMetadata) -> VideoSlot | None:
    """Pick the stronger video: higher views when both reported, otherwise likes."""
    if a.views > 0 and b.views > 0 and a.views != b.views:
        return "A" if a.views > b.views else "B"
    if a.likes != b.likes:
        return "A" if a.likes > b.likes else "B"
    return None


def performance_delta(
    a: VideoMetadata, b: VideoMetadata, winner: VideoSlot | None
) -> float:
    """Margin of victory: view gap when views decided the winner, else like gap."""
    if winner is None:
        return 0.0
    hi, lo = (a, b) if winner == "A" else (b, a)
    if a.views > 0 and b.views > 0 and a.views != b.views:
        return float(hi.views - lo.views)
    return float(hi.likes - lo.likes)


def winner_lead_summary(
    a: VideoMetadata, b: VideoMetadata, winner: VideoSlot | None
) -> str:
    if winner is None:
        return "Both videos show comparable views and likes."
    hi, lo = (a, b) if winner == "A" else (b, a)
    if a.views > 0 and b.views > 0 and a.views != b.views:
        return (
            f"Video {winner} leads on views ({hi.views:,} vs {lo.views:,}) "
            f"and likes ({hi.likes:,} vs {lo.likes:,})."
        )
    return f"Video {winner} leads on likes ({hi.likes:,} vs {lo.likes:,})."


def winner_decided_by_views(a: VideoMetadata, b: VideoMetadata) -> bool:
    return a.views > 0 and b.views > 0 and a.views != b.views
