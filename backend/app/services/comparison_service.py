"""Comparison & intelligence service.

Computes the engagement rate and derives strategist-grade signals (hook, CTA,
pacing, topic overlap, recommendations) that power both the dashboard summary
and the RAG context. This is the layer that lets Vanadium explain *why* one
video outperforms another rather than only reporting numbers.
"""

from __future__ import annotations

from app.models.schemas import (
    ComparisonInsights,
    TranscriptSegment,
    VideoMetadata,
    VideoSlot,
)
from app.utils.text import clean_text, first_n_seconds_text, has_cta, keywords


def compute_engagement_rate(likes: int, comments: int, views: int) -> float:
    """engagement_rate = ((likes + comments) / views) * 100."""
    if views <= 0:
        return 0.0
    return round(((likes + comments) / views) * 100, 2)


def _segments_to_pairs(segments: list[TranscriptSegment]) -> list[tuple[str, float]]:
    return [(s.text, s.start) for s in segments]


def _full_text(segments: list[TranscriptSegment]) -> str:
    return clean_text(" ".join(s.text for s in segments))


def _words_per_second(segments: list[TranscriptSegment]) -> float:
    if not segments:
        return 0.0
    total_words = sum(len(s.text.split()) for s in segments)
    end = segments[-1].start + segments[-1].duration
    return round(total_words / end, 2) if end > 0 else 0.0


class ComparisonService:
    def build_insights(
        self,
        video_a: VideoMetadata,
        video_b: VideoMetadata,
        segments_a: list[TranscriptSegment],
        segments_b: list[TranscriptSegment],
    ) -> ComparisonInsights:
        hook_a = first_n_seconds_text(_segments_to_pairs(segments_a))
        hook_b = first_n_seconds_text(_segments_to_pairs(segments_b))

        text_a = _full_text(segments_a)
        text_b = _full_text(segments_b)
        cta_a = has_cta(text_a)
        cta_b = has_cta(text_b)

        winner = self._winner(video_a, video_b)
        delta = round(abs(video_a.engagement_rate - video_b.engagement_rate), 2)

        insights = self._headlines(
            video_a, video_b, hook_a, hook_b, cta_a, cta_b,
            text_a, text_b, segments_a, segments_b, winner,
        )

        return ComparisonInsights(
            winner=winner,
            engagement_delta=delta,
            headline_insights=insights,
            hook_a=hook_a,
            hook_b=hook_b,
            cta_a=cta_a,
            cta_b=cta_b,
        )

    @staticmethod
    def _winner(a: VideoMetadata, b: VideoMetadata) -> VideoSlot | None:
        if a.engagement_rate == b.engagement_rate:
            return None
        return "A" if a.engagement_rate > b.engagement_rate else "B"

    def _headlines(
        self,
        a: VideoMetadata,
        b: VideoMetadata,
        hook_a: str,
        hook_b: str,
        cta_a: bool,
        cta_b: bool,
        text_a: str,
        text_b: str,
        seg_a: list[TranscriptSegment],
        seg_b: list[TranscriptSegment],
        winner: VideoSlot | None,
    ) -> list[str]:
        out: list[str] = []

        if winner:
            hi, lo = (a, b) if winner == "A" else (b, a)
            out.append(
                f"Video {winner} leads on engagement "
                f"({hi.engagement_rate}% vs {lo.engagement_rate}%)."
            )
        else:
            out.append("Both videos have comparable engagement rates.")

        # Hook contrast.
        if hook_a and hook_b:
            qa = "?" in hook_a
            qb = "?" in hook_b
            if qa and not qb:
                out.append("Video A's hook opens with a question; Video B does not.")
            elif qb and not qa:
                out.append("Video B's hook opens with a question; Video A does not.")
            else:
                out.append("Both hooks set up the topic within the first 5 seconds.")
        elif hook_a or hook_b:
            present = "A" if hook_a else "B"
            out.append(f"Only Video {present} has a transcribed opening hook to analyse.")

        # CTA contrast.
        if cta_a != cta_b:
            with_cta = "A" if cta_a else "B"
            out.append(f"Video {with_cta} includes an explicit call-to-action.")
        elif cta_a and cta_b:
            out.append("Both videos include a call-to-action.")

        # Pacing.
        wps_a, wps_b = _words_per_second(seg_a), _words_per_second(seg_b)
        if wps_a and wps_b:
            faster = "A" if wps_a > wps_b else "B"
            out.append(
                f"Video {faster} is more fast-paced "
                f"({wps_a} vs {wps_b} words/sec)."
            )

        # Topic overlap.
        ka, kb = set(keywords(text_a)), set(keywords(text_b))
        if ka and kb:
            shared = sorted(ka & kb)[:5]
            if shared:
                out.append("Shared themes: " + ", ".join(shared) + ".")

        # Reach context.
        if a.follower_count and b.follower_count and a.follower_count != b.follower_count:
            bigger = "A" if a.follower_count > b.follower_count else "B"
            out.append(f"Video {bigger}'s creator has a larger following.")

        return out


comparison_service = ComparisonService()
