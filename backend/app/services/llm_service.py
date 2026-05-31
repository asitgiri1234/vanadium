"""Unified LLM provider (OpenAI or Groq).

Groq uses an OpenAI-compatible API at https://api.groq.com/openai/v1.
Text tasks use llama-3.3-70b-versatile; vision uses llama-4-scout (multimodal).
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_text_llm(*, temperature: float = 0.3, streaming: bool = False) -> BaseChatModel:
    """Chat model for comparison, chat, and other text-only tasks."""
    from langchain_openai import ChatOpenAI

    if settings.llm_provider == "groq":
        return ChatOpenAI(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            temperature=temperature,
            streaming=streaming,
        )

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
        streaming=streaming,
    )


def get_vision_llm(*, temperature: float = 0.2) -> BaseChatModel:
    """Multimodal model for frame analysis (scene + on-screen text)."""
    from langchain_openai import ChatOpenAI

    if settings.llm_provider == "groq":
        return ChatOpenAI(
            model=settings.groq_vision_model,
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            temperature=temperature,
        )

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )
