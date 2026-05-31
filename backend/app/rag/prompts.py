"""Prompt templates and context assembly for the RAG analyst."""

from __future__ import annotations

from app.models.schemas import AnalysisSnapshot, Citation, VideoMetadata

SYSTEM_PROMPT = """\
You are Vanadium, an expert AI content strategist for social media creators.
You compare two videos (Video A and Video B) and explain, with evidence, why \
one performs better than the other, then give actionable advice.

Rules:
- Ground every claim in the provided METADATA, TRANSCRIPT EVIDENCE, and VISUAL EVIDENCE.
- When you use a transcript chunk, reference it inline like [A#4] or [B#2] \
using the handles shown in the evidence. Visual evidence uses [A#visual] or [B#visual].
- Be specific and strategic: talk about hooks, CTAs, pacing, structure, topic, \
on-screen text, visuals, and engagement — not just raw numbers.
- If evidence is missing (e.g. no transcript), say so plainly instead of \
inventing details.
- Keep answers concise, skimmable, and oriented toward helping the creator \
improve future content.
"""


def _metadata_block(v: VideoMetadata) -> str:
    tags = ", ".join(v.hashtags) if v.hashtags else "none"
    return (
        f"Video {v.video_id} ({v.platform.value})\n"
        f"  title: {v.title}\n"
        f"  creator: {v.creator} (followers: {v.follower_count:,})\n"
        f"  views: {v.views:,} | likes: {v.likes:,} | comments: {v.comments:,}\n"
        f"  engagement_rate: {v.engagement_rate}%\n"
        f"  duration: {v.duration_seconds}s | uploaded: {v.upload_date or 'unknown'}\n"
        f"  hashtags: {tags}\n"
        f"  transcript_available: {v.transcript_available}"
    )


def _evidence_block(citations: list[Citation]) -> str:
    if not citations:
        return "No transcript or visual evidence retrieved for this question."
    lines = []
    for c in citations:
        if c.chunk_index == -1:
            handle = f"[{c.video_id}#visual]"
        else:
            handle = f"[{c.video_id}#{c.chunk_index}]"
        snippet = (c.snippet or "").strip()
        if len(snippet) > 500:
            snippet = snippet[:500] + "…"
        lines.append(f"{handle} (Video {c.video_id} {c.timestamp}): {snippet}")
    return "\n".join(lines)


def build_context(
    snapshot: AnalysisSnapshot,
    citations: list[Citation],
    *,
    transcript_excerpts: dict[str, str] | None = None,
) -> str:
    a = snapshot.videos["A"]
    b = snapshot.videos["B"]
    comp = snapshot.comparison

    headline = "\n".join(f"  - {i}" for i in comp.headline_insights) or "  - n/a"
    winner = comp.winner or "tie"
    recs = "\n".join(f"  - {r}" for r in comp.recommendations) or "  - n/a"

    baseline = ""
    if transcript_excerpts:
        baseline = (
            "BASELINE TRANSCRIPT EXCERPTS (full opening — use when retrieval is sparse)\n"
            f"  Video A: {transcript_excerpts.get('A', 'none')}\n"
            f"  Video B: {transcript_excerpts.get('B', 'none')}\n\n"
        )

    return (
        "METADATA\n"
        f"{_metadata_block(a)}\n\n"
        f"{_metadata_block(b)}\n\n"
        "COMPARISON SUMMARY\n"
        f"  engagement winner: Video {winner} (delta {comp.engagement_delta} pts)\n"
        f"  hook A: {comp.hook_a or 'n/a'}\n"
        f"  hook B: {comp.hook_b or 'n/a'}\n"
        f"  CTA present — A: {comp.cta_a}, B: {comp.cta_b}\n"
        f"  headline insights:\n{headline}\n"
        f"  strategist summary: {comp.strategist_summary or 'n/a'}\n"
        f"  recommendations:\n{recs}\n\n"
        f"{baseline}"
        "EVIDENCE (transcript + visual)\n"
        f"{_evidence_block(citations)}"
    )


def build_user_prompt(context: str, question: str) -> str:
    return (
        f"{context}\n\n"
        "----\n"
        f"CREATOR QUESTION: {question}\n\n"
        "Answer as Vanadium, citing evidence handles where relevant."
    )
