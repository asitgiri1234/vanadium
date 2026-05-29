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
from app.models.schemas import AnalysisSnapshot, Citation
from app.rag.citations import select_cited
from app.rag.prompts import SYSTEM_PROMPT, build_context, build_user_prompt
from app.rag.retriever import retriever
from app.store.analysis_store import analysis_store

logger = get_logger(__name__)


class ChatService:
    async def stream(self, analysis_id: str, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = analysis_store.get(analysis_id)
        if snapshot is None:
            yield {"type": "error", "detail": f"Unknown analysis_id: {analysis_id}"}
            return

        citations = retriever.retrieve(message, analysis_id)
        context = build_context(snapshot, citations)
        user_prompt = build_user_prompt(context, message)
        history = analysis_store.get_memory(analysis_id)

        answer_parts: list[str] = []
        try:
            if settings.openai_configured:
                async for token in self._stream_openai(user_prompt, history):
                    answer_parts.append(token)
                    yield {"type": "token", "text": token}
            else:
                for token in self._extractive_answer(snapshot, citations, message):
                    answer_parts.append(token)
                    yield {"type": "token", "text": token}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Generation failed")
            yield {"type": "error", "detail": f"Generation failed: {exc}"}
            return

        answer = "".join(answer_parts).strip()
        cited = select_cited(answer, citations)

        analysis_store.append_turn(analysis_id, "user", message)
        analysis_store.append_turn(analysis_id, "assistant", answer)

        yield {"type": "citations", "data": [c.model_dump(mode="json") for c in cited]}
        yield {"type": "done", "message_id": "m_" + uuid.uuid4().hex[:8]}

    # ----------------------------------------------------------------- #
    # OpenAI streaming via LangChain
    # ----------------------------------------------------------------- #
    async def _stream_openai(self, user_prompt: str, history) -> AsyncIterator[str]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
            streaming=True,
        )

        messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        for turn in history:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            else:
                messages.append(AIMessage(content=turn.content))
        messages.append(HumanMessage(content=user_prompt))

        async for chunk in llm.astream(messages):
            text = getattr(chunk, "content", "") or ""
            if text:
                yield text

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
        winner = comp.winner
        if winner:
            hi, lo = (a, b) if winner == "A" else (b, a)
            lines.append(
                f"Video {winner} is the stronger performer: {hi.engagement_rate}% "
                f"engagement vs {lo.engagement_rate}% for the other "
                f"(a {comp.engagement_delta}-point gap)."
            )
        else:
            lines.append(
                f"Both videos show similar engagement "
                f"(A: {a.engagement_rate}%, B: {b.engagement_rate}%)."
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
