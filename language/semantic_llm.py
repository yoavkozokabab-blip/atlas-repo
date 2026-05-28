"""Optional local LLM semantic planner (JSON only, classification aid)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from config import (
    IMPLEMENTED_INTENTS,
    SEMANTIC_LLM_MODEL,
    SEMANTIC_LLM_PROVIDER,
    SEMANTIC_LLM_TIMEOUT_SECONDS,
    SEMANTIC_MIN_CONFIDENCE,
)
from core.logger import setup_logger
from language.semantic_context import SemanticContext

logger = setup_logger("jarvis.language.semantic_llm")

_FORBIDDEN_KEYS = frozenset(
    {"shell", "command", "powershell", "python", "code", "script", "execute", "path_to_run"}
)


@dataclass(frozen=True)
class SemanticLlmResult:
    intent: str
    canonical_command: str
    confidence: float
    requires_confirmation: bool
    clarification: str
    reason: str
    valid: bool


def _system_prompt() -> str:
    intents = ", ".join(sorted(IMPLEMENTED_INTENTS)[:80])
    more = len(IMPLEMENTED_INTENTS) - 80
    suffix = f" ... (+{more} more)" if more > 0 else ""
    return (
        "You map user voice commands to JARVIS intents. "
        "Respond with JSON only. Never execute actions. "
        f"Allowed intent values: {intents}{suffix}. "
        "If unsure, set intent to clarify and provide clarification text."
    )


def _build_user_prompt(
    text: str,
    *,
    normalized: str,
    ctx: SemanticContext,
) -> str:
    payload = {
        "raw_transcript": text[:400],
        "normalized_transcript": normalized[:400],
        "last_intent": ctx.last_intent,
        "workspace_mode": ctx.workspace_mode,
        "active_app": ctx.active_app,
        "screen_summary": ctx.screen_summary[:200],
    }
    return (
        "Classify this command.\n"
        f"{json.dumps(payload, ensure_ascii=True)}\n\n"
        "Return JSON with keys: intent, canonical_command, confidence, "
        "requires_confirmation, clarification, reason."
    )


def _has_forbidden(obj: Any, depth: int = 0) -> bool:
    if depth > 4:
        return True
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                return True
            if _has_forbidden(v, depth + 1):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _has_forbidden(item, depth + 1):
                return True
    return False


def validate_semantic_llm_payload(payload: dict[str, Any]) -> SemanticLlmResult:
    if _has_forbidden(payload):
        return SemanticLlmResult(
            intent="clarify",
            canonical_command="",
            confidence=0.0,
            requires_confirmation=False,
            clarification="Invalid LLM response shape.",
            reason="forbidden_key",
            valid=False,
        )
    intent_raw = str(payload.get("intent") or "").strip().lower()
    if intent_raw in {"unknown", "clarify", "clarification_needed", ""}:
        return SemanticLlmResult(
            intent="clarify",
            canonical_command=str(payload.get("canonical_command") or "")[:200],
            confidence=float(payload.get("confidence") or 0.0),
            requires_confirmation=False,
            clarification=str(payload.get("clarification") or "Please rephrase.")[:300],
            reason=str(payload.get("reason") or "clarification")[:200],
            valid=False,
        )
    if intent_raw not in IMPLEMENTED_INTENTS:
        return SemanticLlmResult(
            intent="clarify",
            canonical_command="",
            confidence=0.0,
            requires_confirmation=False,
            clarification=f"I cannot run '{intent_raw}'. Please use a supported command.",
            reason="intent_not_implemented",
            valid=False,
        )
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    if confidence < SEMANTIC_MIN_CONFIDENCE:
        return SemanticLlmResult(
            intent="clarify",
            canonical_command=str(payload.get("canonical_command") or "")[:200],
            confidence=confidence,
            requires_confirmation=False,
            clarification=str(payload.get("clarification") or "Low confidence — please confirm.")[:300],
            reason=str(payload.get("reason") or "low_confidence")[:200],
            valid=False,
        )
    return SemanticLlmResult(
        intent=intent_raw,
        canonical_command=str(payload.get("canonical_command") or "")[:200],
        confidence=confidence,
        requires_confirmation=bool(payload.get("requires_confirmation")),
        clarification=str(payload.get("clarification") or "")[:300],
        reason=str(payload.get("reason") or "")[:200],
        valid=True,
    )


def plan_with_semantic_llm(
    text: str,
    *,
    normalized: str,
    ctx: SemanticContext,
) -> SemanticLlmResult:
    """Call local Ollama for semantic JSON; never executes commands."""
    provider = (SEMANTIC_LLM_PROVIDER or "ollama").strip().lower()
    if provider != "ollama":
        return SemanticLlmResult(
            intent="clarify",
            canonical_command="",
            confidence=0.0,
            requires_confirmation=False,
            clarification="Semantic LLM provider not supported.",
            reason=f"unsupported_provider:{provider}",
            valid=False,
        )
    try:
        from integrations.ollama_client import OllamaClient, OllamaError

        client = OllamaClient(
            model=SEMANTIC_LLM_MODEL,
            timeout=int(SEMANTIC_LLM_TIMEOUT_SECONDS),
        )
        payload = client.classify_intent(
            _build_user_prompt(text, normalized=normalized, ctx=ctx),
            system=_system_prompt(),
        )
        if not isinstance(payload, dict):
            raise OllamaError("Semantic LLM did not return a JSON object")
        return validate_semantic_llm_payload(payload)
    except Exception as exc:
        logger.warning("Semantic LLM failed: %s", exc)
        return SemanticLlmResult(
            intent="clarify",
            canonical_command="",
            confidence=0.0,
            requires_confirmation=False,
            clarification="I could not interpret that clearly. Please rephrase.",
            reason=str(exc)[:200],
            valid=False,
        )
