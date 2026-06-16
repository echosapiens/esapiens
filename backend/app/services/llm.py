"""LLM client for OpenRouter-backed inference.

OpenRouter speaks the OpenAI API protocol, so we use langchain-openai's
ChatOpenAI with a custom base_url. The model is configurable via
OPENROUTER_MODEL (default: anthropic/claude-sonnet-4).

When OPENROUTER_API_KEY is empty or unset, the client returns None
and the agent falls back to deterministic rule-based planning.
"""

from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_llm_instance: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI | None:
    """Return a singleton ChatOpenAI client pointed at OpenRouter.

    Returns None if OPENROUTER_API_KEY is not configured, signalling
    callers to use the rule-based fallback.
    """
    global _llm_instance

    if not settings.OPENROUTER_API_KEY:
        logger.debug("OPENROUTER_API_KEY not set — LLM unavailable, using rule-based fallback")
        return None

    if _llm_instance is not None:
        return _llm_instance

    _llm_instance = ChatOpenAI(
        model=settings.OPENROUTER_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        temperature=0.2,
        max_tokens=4096,
        default_headers={
            "HTTP-Referer": "https://esapiens.io",
            "X-Title": "E.sapiens",
        },
    )

    logger.info("OpenRouter LLM initialized: model=%s", settings.OPENROUTER_MODEL)
    return _llm_instance


def reset_llm() -> None:
    """Reset the singleton — used in tests or when config changes."""
    global _llm_instance
    _llm_instance = None