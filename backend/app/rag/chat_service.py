"""Streaming RAG chat service.

Orchestrates a single chat turn:

    snapshot + memory + retrieved chunks → prompt → streamed LLM answer → citations

Emits a sequence of typed events consumed by the SSE endpoint. When OpenAI is
not configured it streams a deterministic, evidence-based extractive answer so
the product remains fully functional offline.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import AnalysisSnapshot, Citation, TranscriptSegment
from app.rag.citations import select_cited
from app.rag.off_topic import OFF_TOPIC_REPLY, is_off_topic_message
from app.rag.prompts import SYSTEM_PROMPT, build_context, build_user_prompt
from app.rag.retriever import retriever
from app.services.embedding_service import embedding_service
from app.store.analysis_store import analysis_store
from app.utils.formatting import fmt_count
from app.utils.performance import (
    determine_winner,
    performance_delta,
    winner_decided_by_views,
    winner_lead_summary,
)

logger = get_logger(__name__)


class ChatService:
    async def stream(self, analysis_id: str, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = analysis_store.get(analysis_id)
        if snapshot is None:
            yield {"type": "error", "detail": f"Unknown analysis_id: {analysis_id}"}
            return

        if is_off_topic_message(message):
            answer = OFF_TOPIC_REPLY
            async for token in self._yield_words(answer):
                yield {"type": "token", "text": token}
            analysis_store.append_turn(analysis_id, "user", message)
            analysis_store.append_turn(analysis_id, "assistant", answer)
            yield {"type": "citations", "data": []}
            yield {"type": "done", "message_id": "m_" + uuid.uuid4().hex[:8]}
            return

        answer_parts: list[str] = []
        citations: list[Citation] = []
        try:
            # Retrieval can fail (e.g. vector store unavailable); keep it inside
            # the guard so it degrades to an error event instead of killing the
            # SSE stream and showing a blank reply.
            citations = retriever.retrieve(message, analysis_id)
            transcript_excerpts = self._baseline_transcript_excerpts(analysis_id)
            context = build_context(
                snapshot,
                citations,
                transcript_excerpts=transcript_excerpts
                if not embedding_service.using_openai
                else None,
            )
            user_prompt = build_user_prompt(context, message)
            history = analysis_store.get_memory(analysis_id)

            if settings.llm_configured:
                async for token in self._stream_llm(user_prompt, history):
                    answer_parts.append(token)
                    yield {"type": "token", "text": token}
            else:
                for token in self._extractive_answer(snapshot, citations, message):
                    answer_parts.append(token)
                    yield {"type": "token", "text": token}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Generation failed for analysis %s", analysis_id)
            fallback = (
                "I hit a snag answering that — your analysis is still loaded. "
                "Please ask again about Video A vs Video B (hooks, pacing, engagement, etc.)."
            )
            async for token in self._yield_words(fallback):
                yield {"type": "token", "text": token}
            analysis_store.append_turn(analysis_id, "user", message)
            analysis_store.append_turn(analysis_id, "assistant", fallback)
            yield {"type": "citations", "data": []}
            yield {"type": "done", "message_id": "m_" + uuid.uuid4().hex[:8]}
            return

        answer = "".join(answer_parts).strip()
        if settings.llm_configured and not answer:
            fallback = (
                "I couldn't generate an answer for that — try rephrasing your question "
                "about Video A vs Video B (e.g. hooks, CTAs, or engagement)."
            )
            async for token in self._yield_words(fallback):
                yield {"type": "token", "text": token}
            analysis_store.append_turn(analysis_id, "user", message)
            analysis_store.append_turn(analysis_id, "assistant", fallback)
            yield {"type": "citations", "data": []}
            yield {"type": "done", "message_id": "m_" + uuid.uuid4().hex[:8]}
            return

        cited = select_cited(answer, citations)

        analysis_store.append_turn(analysis_id, "user", message)
        analysis_store.append_turn(analysis_id, "assistant", answer)

        yield {"type": "citations", "data": [c.model_dump(mode="json") for c in cited]}
        yield {"type": "done", "message_id": "m_" + uuid.uuid4().hex[:8]}

    # ----------------------------------------------------------------- #
    # LLM streaming via LangChain
    # ----------------------------------------------------------------- #
    async def _stream_llm(self, user_prompt: str, history) -> AsyncIterator[str]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        from app.services.llm_service import get_text_llm
        from app.utils.llm_utils import content_to_text

        messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        for turn in history:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            else:
                messages.append(AIMessage(content=turn.content))
        messages.append(HumanMessage(content=user_prompt))

        # Groq/LangChain streaming often yields empty chunks; invoke-first is reliable.
        if settings.llm_provider.lower() == "groq":
            llm = get_text_llm(temperature=0.3, streaming=False)
            resp = await llm.ainvoke(messages)
            text = content_to_text(getattr(resp, "content", None)).strip()
            if text:
                async for token in self._yield_words(text):
                    yield token
            return

        llm = get_text_llm(temperature=0.3, streaming=True)
        emitted = False
        async for chunk in llm.astream(messages):
            text = content_to_text(getattr(chunk, "content", None))
            if text:
                emitted = True
                yield text

        if not emitted:
            fallback = get_text_llm(temperature=0.3, streaming=False)
            resp = await fallback.ainvoke(messages)
            text = content_to_text(getattr(resp, "content", None))
            if text:
                yield text

    @staticmethod
    async def _yield_words(text: str) -> AsyncIterator[str]:
        words = text.split(" ")
        for i, w in enumerate(words):
            yield w if i == 0 else " " + w

    @staticmethod
    def _baseline_transcript_excerpts(
        analysis_id: str,
    ) -> dict[str, str] | None:
        """First ~400 chars of each video transcript for hash-embedding fallback."""
        stored = analysis_store.get_transcripts(analysis_id)
        if not stored:
            return None

        excerpts: dict[str, str] = {}
        for slot in ("A", "B"):
            segments: list[TranscriptSegment] = stored.get(slot)  # type: ignore[arg-type]
            if not segments:
                excerpts[slot] = "none"
                continue
            full = " ".join(s.text for s in segments).strip()
            if len(full) > 400:
                full = full[:400] + "…"
            excerpts[slot] = full or "none"
        return excerpts

    # ----------------------------------------------------------------- #
    # Offline deterministic analyst
    # ----------------------------------------------------------------- #
    @staticmethod
    def _extractive_answer(
        snapshot: AnalysisSnapshot, citations: list[Citation], question: str
    ):
        a = snapshot.videos["A"]
        b = snapshot.videos["B"]
        comp = snapshot.comparison

        lines: list[str] = []
        winner = determine_winner(a, b)
        if winner:
            hi, lo = (a, b) if winner == "A" else (b, a)
            delta = performance_delta(a, b, winner)
            metric = "views" if winner_decided_by_views(a, b) else "likes"
            lines.append(
                f"Video {winner} is the stronger performer: "
                f"{hi.views:,} views / {fmt_count(hi.likes)} likes vs "
                f"{lo.views:,} views / {fmt_count(lo.likes)} likes "
                f"({delta:,.0f} {metric} margin)."
            )
            lines.append(winner_lead_summary(a, b, winner))
        else:
            lines.append(
                f"Both videos show comparable performance "
                f"(A: {a.views:,} views / {fmt_count(a.likes)} likes · "
                f"B: {b.views:,} views / {fmt_count(b.likes)} likes)."
            )

        if comp.headline_insights:
            lines.append("Key drivers:")
            lines.extend(f"- {i}" for i in comp.headline_insights)

        if comp.hook_a or comp.hook_b:
            lines.append(
                f'Hooks — A: "{comp.hook_a or "n/a"}" | B: "{comp.hook_b or "n/a"}".'
            )

        weaker = "B" if winner == "A" else ("A" if winner == "B" else None)
        if weaker:
            lines.append(
                f"Recommendation for Video {weaker}: mirror what works in the leader — "
                "a sharper first-5-second hook, a clear call-to-action, and tighter pacing."
            )

        if citations:
            handles = ", ".join(
                f"[{c.video_id}#{c.chunk_index}]" for c in citations[:4]
            )
            lines.append(f"Supporting transcript evidence: {handles}.")
        else:
            lines.append(
                "Note: no transcript was available for retrieval, so this is based on "
                "metadata and engagement signals only."
            )

        text = "\n".join(lines)
        # Stream word-by-word to mimic token streaming in the UI.
        words = text.split(" ")
        for i, w in enumerate(words):
            yield (w if i == 0 else " " + w)


chat_service = ChatService()
