"""RAG retrieval.

Balanced retrieval: we fetch top-k chunks *per video* so the model always sees
both sides of the comparison, then deduplicate while preserving order. Falls
back to a single-pool query if a per-video query yields nothing.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Citation
from app.services.embedding_service import embedding_service
from app.vectorstore.chroma_store import chroma_store

logger = get_logger(__name__)


class Retriever:
    def retrieve(
        self, question: str, analysis_id: str, top_k: int | None = None
    ) -> list[Citation]:
        k = top_k or settings.retrieval_top_k
        query_embedding = embedding_service.embed_query(question)

        citations: list[Citation] = []
        for slot in ("A", "B"):
            citations.extend(
                chroma_store.query(
                    query_embedding=query_embedding,
                    analysis_id=analysis_id,
                    video_id=slot,  # type: ignore[arg-type]
                    top_k=k,
                    record_types=["transcript", "visual"],
                )
            )

        # Fallback: unfiltered-by-video pool if balanced retrieval was empty.
        if not citations:
            citations = chroma_store.query(
                query_embedding=query_embedding,
                analysis_id=analysis_id,
                video_id=None,
                top_k=k * 2,
                record_types=["transcript", "visual"],
            )

        return self._dedupe(citations)

    @staticmethod
    def _dedupe(citations: list[Citation]) -> list[Citation]:
        seen: set[tuple[str, int]] = set()
        out: list[Citation] = []
        for c in citations:
            key = (c.video_id, c.chunk_index)
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out


retriever = Retriever()
