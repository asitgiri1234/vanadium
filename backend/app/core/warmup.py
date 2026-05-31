"""Eager-load heavy native deps before parallel ingest threads start.

ChromaDB and Whisper both pull in NumPy. Lazy-importing them from multiple
threads at once triggers "partially initialized module numpy._typing" errors.
"""

from __future__ import annotations

import threading

_warmed = False
_lock = threading.Lock()


def warmup_heavy_dependencies() -> None:
    """Import NumPy/Chroma (and optionally Whisper) once on the main thread."""
    global _warmed
    if _warmed:
        return
    with _lock:
        if _warmed:
            return
        import numpy  # noqa: F401 — must finish before chromadb/whisper threads

        from app.vectorstore.chroma_store import chroma_store

        chroma_store.warmup()

        from app.core.config import settings

        if settings.enable_whisper and settings.whisper_provider.lower() == "local":
            import whisper  # noqa: F401

        _warmed = True
