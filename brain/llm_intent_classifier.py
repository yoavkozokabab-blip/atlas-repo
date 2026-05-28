"""LLM-assisted intent classification with strict validation."""

from __future__ import annotations

import re
from typing import Any

from config import IMPLEMENTED_INTENTS, LLM_MIN_CONFIDENCE, LLM_PROVIDER
from brain.prompts import INTENT_CLASSIFICATION_SYSTEM, build_intent_classification_prompt
from core.types import Intent, IntentClassification
from integrations.ollama_client import OllamaClient, OllamaError

from core.logger import setup_logger

logger = setup_logger("jarvis.llm_classifier")

FORBIDDEN_JSON_KEYS = frozenset(
    {
        "shell",
        "command",
        "powershell",
        "python",
        "code",
        "script",
        "execute",
        "path_to_run",
    }
)

ALLOWED_PARAM_KEYS = frozenset(
    {"query", "name", "key", "path", "search_query"}
)


def _has_forbidden_keys(obj: Any, *, depth: int = 0) -> bool:
    if depth > 5:
        return True
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_JSON_KEYS:
                return True
            if _has_forbidden_keys(v, depth=depth + 1):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _has_forbidden_keys(item, depth=depth + 1):
                return True
    return False


def _sanitize_params(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, value in params.items():
        k = str(key)
        if k.lower() in FORBIDDEN_JSON_KEYS:
            continue
        if k in ALLOWED_PARAM_KEYS or k.isidentifier():
            if isinstance(value, (str, int, float, bool)):
                clean[k] = value
            elif value is not None:
                clean[k] = str(value)[:200]
    return clean


def validate_llm_payload(payload: dict[str, Any]) -> IntentClassification:
    """Validate LLM JSON; return invalid classification on failure."""
    if _has_forbidden_keys(payload):
        return IntentClassification(
            intent=Intent.CLARIFY.value,
            confidence=0.0,
            reason="Forbidden key in LLM response",
            classifier_source="clarification",
            valid=False,
        )

    intent_raw = str(payload.get("intent") or "").strip().lower()
    if intent_raw in {"clarification_needed", "clarify", "unknown"}:
        return IntentClassification(
            intent=Intent.CLARIFY.value,
            confidence=float(payload.get("confidence") or 0.0),
            params=_sanitize_params(payload.get("params")),
            reason=str(payload.get("reason") or "LLM requested clarification"),
            classifier_source="clarification",
            valid=False,
        )

    if intent_raw not in IMPLEMENTED_INTENTS:
        return IntentClassification(
            intent=Intent.CLARIFY.value,
            confidence=0.0,
            reason=f"Intent '{intent_raw}' not in allowlist",
            classifier_source="clarification",
            valid=False,
        )

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    if confidence < LLM_MIN_CONFIDENCE:
        return IntentClassification(
            intent=Intent.CLARIFY.value,
            confidence=confidence,
            params=_sanitize_params(payload.get("params")),
            reason=str(payload.get("reason") or "Low LLM confidence"),
            classifier_source="clarification",
            valid=False,
        )

    return IntentClassification(
        intent=intent_raw,
        confidence=confidence,
        params=_sanitize_params(payload.get("params")),
        reason=str(payload.get("reason") or "")[:200],
        classifier_source="llm",
        valid=True,
    )


class LLMIntentClassifier:
    """Classify user text via local Ollama (JSON only)."""

    def __init__(self, client: OllamaClient | None = None) -> None:
        self._client = client

    def _get_client(self) -> OllamaClient:
        if self._client is not None:
            return self._client
        if LLM_PROVIDER != "ollama":
            raise OllamaError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")
        return OllamaClient()

    def classify(
        self,
        raw_text: str,
        session_context: dict | None = None,
    ) -> IntentClassification:
        """Call LLM and return validated IntentClassification."""
        text = raw_text.strip()
        if not text:
            return IntentClassification(
                intent=Intent.UNKNOWN.value,
                confidence=0.0,
                reason="Empty input",
                classifier_source="clarification",
                valid=False,
            )

        prompt = build_intent_classification_prompt(text, session_context=session_context)
        try:
            payload = self._get_client().classify_intent(
                prompt,
                system=INTENT_CLASSIFICATION_SYSTEM,
            )
        except OllamaError as exc:
            logger.warning("LLM classification failed: %s", exc)
            return IntentClassification(
                intent=Intent.CLARIFY.value,
                confidence=0.0,
                reason=str(exc),
                classifier_source="clarification",
                valid=False,
            )

        if not isinstance(payload, dict):
            return IntentClassification(
                intent=Intent.CLARIFY.value,
                confidence=0.0,
                reason="LLM response not a dict",
                classifier_source="clarification",
                valid=False,
            )

        return validate_llm_payload(payload)


def classification_to_request(
    raw_text: str,
    classification: IntentClassification,
) -> "CommandRequest":
    """Convert validated classification to CommandRequest."""
    from core.types import CommandRequest

    intent_value = classification.intent
    try:
        intent = Intent(intent_value)
    except ValueError:
        intent = Intent.CLARIFY

    language = "he" if re.search(r"[\u0590-\u05FF]", raw_text) else "en"
    return CommandRequest(
        raw_text=raw_text,
        intent=intent,
        confidence=classification.confidence,
        params=dict(classification.params),
        language=language,
        classifier_source=classification.classifier_source,
    )
