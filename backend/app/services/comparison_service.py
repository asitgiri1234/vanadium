"""Comparison & intelligence service.

Computes the engagement rate and derives strategist-grade signals (hook, CTA,
pacing, topic overlap, recommendations) that power both the dashboard summary
and the RAG context. When OpenAI is configured, an LLM produces a narrative
comparison and actionable recommendations using metadata, transcripts, and
visual analysis.
"""

from __future__ import annotations

import json
import re

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    ComparisonInsights,
    TranscriptSegment,
    VideoMetadata,
    VideoSlot,
    VideoVisual,
)
from app.utils.text import clean_text, first_n_seconds_text, has_cta, keywords

logger = get_logger(__name__)


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


def _visual_block(visual: VideoVisual | None) -> str:
    if not visual or not visual.available:
        return "none"
    parts: list[str] = []
    if visual.visual_summary:
        parts.append(f"scene: {visual.visual_summary}")
    if visual.on_screen_text:
        parts.append(f"on-screen text: {visual.on_screen_text}")
    ocr = " | ".join(f.ocr_text for f in visual.frames if f.ocr_text)
    if ocr:
        parts.append(f"on-screen text (ocr): {ocr}")
    return "; ".join(parts) if parts else "none"


class ComparisonService:
    def build_insights(
        self,
        video_a: VideoMetadata,
        video_b: VideoMetadata,
        segments_a: list[TranscriptSegment],
        segments_b: list[TranscriptSegment],
        visual_a: VideoVisual | None = None,
        visual_b: VideoVisual | None = None,
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
            ai_pending=settings.llm_configured,
        )

    def build_llm_insights(
        self,
        video_a: VideoMetadata,
        video_b: VideoMetadata,
        segments_a: list[TranscriptSegment],
        segments_b: list[TranscriptSegment],
        visual_a: VideoVisual | None = None,
        visual_b: VideoVisual | None = None,
        base: ComparisonInsights | None = None,
    ) -> ComparisonInsights:
        """Run the LLM strategist (slow) — call from a background thread."""
        hook_a = first_n_seconds_text(_segments_to_pairs(segments_a))
        hook_b = first_n_seconds_text(_segments_to_pairs(segments_b))
        text_a = _full_text(segments_a)
        text_b = _full_text(segments_b)
        winner = self._winner(video_a, video_b)

        summary, recommendations = self._llm_strategist(
            video_a, video_b, hook_a, hook_b,
            has_cta(text_a), has_cta(text_b),
            text_a, text_b, winner, visual_a, visual_b,
        )

        if base is None:
            return self.build_insights(
                video_a, video_b, segments_a, segments_b, visual_a, visual_b
            ).model_copy(
                update={
                    "strategist_summary": summary,
                    "recommendations": recommendations,
                    "ai_pending": False,
                }
            )

        return base.model_copy(
            update={
                "strategist_summary": summary,
                "recommendations": recommendations,
                "ai_pending": False,
            }
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

    def _llm_strategist(
        self,
        a: VideoMetadata,
        b: VideoMetadata,
        hook_a: str,
        hook_b: str,
        cta_a: bool,
        cta_b: bool,
        text_a: str,
        text_b: str,
        winner: VideoSlot | None,
        visual_a: VideoVisual | None,
        visual_b: VideoVisual | None,
    ) -> tuple[str, list[str]]:
        """Generate narrative comparison + recommendations via configured LLM."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            from app.services.llm_service import get_text_llm

            winner_label = f"Video {winner}" if winner else "tie (comparable engagement)"
            excerpt_a = (text_a[:400] + "…") if len(text_a) > 400 else (text_a or "none")
            excerpt_b = (text_b[:400] + "…") if len(text_b) > 400 else (text_b or "none")

            user_content = f"""Compare these two social videos as a content strategist.

VIDEO A ({a.platform.value})
- title: {a.title}
- creator: {a.creator} ({a.follower_count:,} followers)
- views: {a.views:,} | likes: {a.likes:,} | comments: {a.comments:,}
- engagement rate: {a.engagement_rate}%
- duration: {a.duration_seconds}s
- hook (first 5s): {hook_a or "n/a"}
- CTA present: {cta_a}
- transcript excerpt: {excerpt_a}
- visual analysis: {_visual_block(visual_a)}

VIDEO B ({b.platform.value})
- title: {b.title}
- creator: {b.creator} ({b.follower_count:,} followers)
- views: {b.views:,} | likes: {b.likes:,} | comments: {b.comments:,}
- engagement rate: {b.engagement_rate}%
- duration: {b.duration_seconds}s
- hook (first 5s): {hook_b or "n/a"}
- CTA present: {cta_b}
- transcript excerpt: {excerpt_b}
- visual analysis: {_visual_block(visual_b)}

Engagement winner: {winner_label}

Respond with valid JSON only (no markdown fences):
{{
  "summary": "2-4 sentences explaining WHY one outperformed the other — hooks, visuals, pacing, topic, CTA, format. Ground claims in the data above.",
  "recommendations": ["3-5 specific actionable tips for improving future content, referencing what worked in the stronger video"]
}}"""

            llm = get_text_llm(temperature=0.4)
            resp = llm.invoke([
                SystemMessage(content=(
                    "You are Vanadium, an expert AI content strategist. "
                    "Compare videos with evidence-backed, creator-friendly advice. "
                    "Respond with valid JSON only."
                )),
                HumanMessage(content=user_content),
            ])
            raw = clean_text(getattr(resp, "content", "") or "")
            summary, recommendations = self._parse_llm_json(raw)
            if not summary and not recommendations:
                raise ValueError(f"LLM returned empty comparison: {raw[:120]}")
            return summary, recommendations
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM comparison failed: %s", exc)
            raise

    @staticmethod
    def _parse_llm_json(raw: str) -> tuple[str, list[str]]:
        """Extract summary + recommendations from LLM JSON output."""
        text = raw.strip()
        # Strip optional ```json fences.
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            summary = clean_text(str(data.get("summary", "")))
            recs = data.get("recommendations") or []
            if isinstance(recs, list):
                recommendations = [clean_text(str(r)) for r in recs if str(r).strip()]
            else:
                recommendations = []
            return summary, recommendations
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM comparison JSON")
            return raw[:1200], []


comparison_service = ComparisonService()
