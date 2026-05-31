"""Citation post-processing.

Given the citations retrieved for a question and the model's answer text, keep
the citations that the model actually referenced (via ``[A#4]`` handles). If the
model referenced none explicitly, return the top retrieved citations so the UI
always shows verifiable sources.
"""

from __future__ import annotations

import re

from app.models.schemas import Citation

_HANDLE_RE = re.compile(r"\[([AB])#(\d+|visual)\]")


def select_cited(answer: str, retrieved: list[Citation], fallback_n: int = 4) -> list[Citation]:
    referenced: set[tuple[str, int]] = set()
    for m in _HANDLE_RE.finditer(answer):
        slot = m.group(1)
        idx_raw = m.group(2)
        idx = -1 if idx_raw == "visual" else int(idx_raw)
        referenced.add((slot, idx))

    if referenced:
        chosen = [c for c in retrieved if (c.video_id, c.chunk_index) in referenced]
        if chosen:
            return chosen

    return retrieved[:fallback_n]
