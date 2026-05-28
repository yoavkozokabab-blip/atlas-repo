"""OpenAI provider stub — optional future LLM classifier backend."""

from __future__ import annotations


class OpenAIClassifierNotConfiguredError(Exception):
    """Raised when OpenAI classification is requested but not implemented."""


def classify_intent(_prompt: str) -> dict:
    raise OpenAIClassifierNotConfiguredError(
        "OpenAI LLM classifier is not implemented. Use LLM_PROVIDER=ollama."
    )
