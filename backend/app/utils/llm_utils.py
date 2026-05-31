"""Helpers for normalising LangChain / Groq / OpenAI LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def content_to_text(content: Any) -> str:
    """Coerce AIMessage.content (str or multimodal block list) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block:
                    parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _JSON_FENCE_RE.sub("", text).strip()
    return text


def _unwrap_json_data(data: Any) -> dict[str, Any]:
    """Accept a dict or a single-element list wrapping a dict."""
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]
    raise ValueError(f"Expected JSON object, got {type(data).__name__}")


def parse_json_object(raw: Any) -> dict[str, Any]:
    """Parse an LLM JSON response, tolerating fences, prose, and list wrappers."""
    text = _strip_fences(content_to_text(raw))

    # Direct parse.
    try:
        return _unwrap_json_data(json.loads(text))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Extract first {...} block from surrounding prose.
    match = _JSON_OBJECT_RE.search(text)
    if match:
        try:
            return _unwrap_json_data(json.loads(match.group(0)))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    raise ValueError(f"Could not parse JSON object from LLM response: {text[:200]!r}")
