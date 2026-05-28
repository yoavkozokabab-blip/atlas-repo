"""Patch workflow command normalization and high-priority classification."""

from __future__ import annotations

import re
import unicodedata

from core.types import CommandRequest, Intent

_PATCH_ALIASES: dict[str, str] = {
    "validate patch safe": "validate patch safety",
    "validate patch": "validate patch safety",
    "patch safety": "validate patch safety",
    "validate patch safety": "validate patch safety",
    "show approved patch": "show approved patch",
    "approved patch": "show approved patch",
    "apply approved patch": "apply approved patch",
    "apply approved patch confirm": "apply approved patch confirm",
    "apply patch confirm": "apply approved patch confirm",
    "rollback last patch": "rollback last patch",
    "rollback last patch confirm": "rollback last patch confirm",
    "rollback patch confirm": "rollback last patch confirm",
    "validate applied patch": "validate applied patch",
    "replay after patch": "replay after patch",
    "replay validation": "replay after patch",
    "replay patch validation": "replay after patch",
    "compare pre post patch": "compare pre post patch",
    "compare pre and post patch": "compare pre post patch",
    "pre post patch": "compare pre post patch",
    "show patch history": "show patch history",
    "run patch workflow": "run patch workflow",
    "run patch workflow confirm": "run patch workflow confirm",
    "show patch workflow status": "show patch workflow status",
    "patch workflow status": "show patch workflow status",
}

_CANONICAL_INTENTS: dict[str, Intent] = {
    "validate patch safety": Intent.VALIDATE_PATCH_SAFETY,
    "show approved patch": Intent.SHOW_APPROVED_PATCH,
    "apply approved patch": Intent.APPLY_APPROVED_PATCH,
    "apply approved patch confirm": Intent.APPLY_APPROVED_PATCH,
    "rollback last patch": Intent.ROLLBACK_LAST_PATCH,
    "rollback last patch confirm": Intent.ROLLBACK_LAST_PATCH,
    "validate applied patch": Intent.VALIDATE_APPLIED_PATCH,
    "replay after patch": Intent.REPLAY_AFTER_PATCH,
    "compare pre post patch": Intent.COMPARE_PRE_POST_PATCH,
    "show patch history": Intent.SHOW_PATCH_HISTORY,
    "run patch workflow": Intent.RUN_PATCH_WORKFLOW,
    "run patch workflow confirm": Intent.RUN_PATCH_WORKFLOW,
    "show patch workflow status": Intent.SHOW_PATCH_WORKFLOW_STATUS,
}

# Exact protected phrases — must never classify as generic run_workflow.
PATCH_PROTECTED_PHRASES: tuple[str, ...] = (
    "run patch workflow",
    "run patch workflow confirm",
    "show patch workflow status",
    "patch workflow status",
    "replay after patch",
    "replay validation",
    "replay patch validation",
    "validate applied patch",
    "validate patch safety",
    "validate patch safe",
    "compare pre post patch",
    "apply approved patch confirm",
    "rollback last patch confirm",
)

_PATCH_WORKFLOW_TIER: tuple[str, ...] = (
    "run patch workflow confirm",
    "run patch workflow",
    "show patch workflow status",
    "patch workflow status",
)

_PATCH_APPLY_TIER: tuple[str, ...] = (
    "apply approved patch confirm",
    "apply approved patch",
    "rollback last patch confirm",
    "rollback last patch",
    "show approved patch",
)

_PATCH_REPLAY_TIER: tuple[str, ...] = (
    "replay after patch",
    "replay validation",
    "replay patch validation",
    "validate applied patch",
    "validate patch safety",
    "validate patch safe",
    "compare pre post patch",
    "compare pre and post patch",
    "show patch history",
)

_GENERIC_WORKFLOW_CAPTURE = re.compile(
    r"run workflow\s+([\w_]+)|(?<!patch\s)workflow\s+([\w_]+)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = re.sub(r"[.!?,;:]+$", "", value).strip()
    return re.sub(r"\s+", " ", value)


def _prepare_text(text: str) -> str:
    try:
        from voice.command_input import prepare_command_text

        return prepare_command_text(text)
    except Exception:
        return text.strip()


def is_patch_workflow_phrase(text: str) -> bool:
    normalized = _normalize(_prepare_text(text))
    if not normalized:
        return False
    if "patch" in normalized and "workflow" in normalized:
        return True
    canonical = normalize_patch_command(text)
    return _normalize(canonical) in _CANONICAL_INTENTS


def normalize_patch_command(text: str) -> str:
    normalized = _normalize(_prepare_text(text))
    if not normalized:
        return ""
    if normalized in _PATCH_ALIASES:
        return _PATCH_ALIASES[normalized]
    if normalized.startswith("apply approved patch") and "confirm" in normalized:
        return "apply approved patch confirm"
    if normalized.startswith("rollback last patch") and "confirm" in normalized:
        return "rollback last patch confirm"
    if normalized.startswith("run patch workflow") and "confirm" in normalized:
        return "run patch workflow confirm"
    if normalized.startswith("validate patch"):
        return "validate patch safety"
    if normalized.startswith("replay") and ("patch" in normalized or normalized in {"replay validation", "replay patch validation"}):
        return "replay after patch"
    if "pre" in normalized and "post" in normalized and "patch" in normalized:
        return "compare pre post patch"
    if normalized.startswith("show patch workflow"):
        return "show patch workflow status"
    if normalized.startswith("run patch workflow"):
        return "run patch workflow"
    return text.strip()


def _request_for_canonical(text: str, canonical: str) -> CommandRequest | None:
    normalized = _normalize(canonical)
    intent = _CANONICAL_INTENTS.get(normalized)
    if intent is None:
        return None
    confirmed = "confirm" in normalized or "confirm" in _normalize(text)
    params: dict[str, object] = {}
    if intent in {Intent.APPLY_APPROVED_PATCH, Intent.ROLLBACK_LAST_PATCH, Intent.RUN_PATCH_WORKFLOW}:
        params["confirmed"] = confirmed
    return CommandRequest(
        raw_text=text,
        intent=intent,
        confidence=0.99,
        params=params,
        confirmed=confirmed,
        classifier_source="patch_workflow",
    )


def match_patch_workflow_commands(text: str) -> CommandRequest | None:
    """
    Highest-priority patch command matcher.

    Priority:
    1. patch workflow commands
    2. patch apply commands
    3. replay / validation commands
    """
    prepared = _prepare_text(text)
    canonical = normalize_patch_command(prepared)
    normalized = _normalize(canonical)
    if normalized in _CANONICAL_INTENTS:
        return _request_for_canonical(prepared, canonical)

    for tier in (_PATCH_WORKFLOW_TIER, _PATCH_APPLY_TIER, _PATCH_REPLAY_TIER):
        for phrase in tier:
            if normalized == phrase or normalized.startswith(phrase):
                mapped = _PATCH_ALIASES.get(phrase, phrase)
                req = _request_for_canonical(prepared, mapped)
                if req is not None:
                    return req
    return None


def match_patch_command(text: str) -> CommandRequest | None:
    """Backward-compatible alias for patch workflow matcher."""
    return match_patch_workflow_commands(text)


def generic_workflow_would_capture(text: str) -> tuple[bool, str]:
    """Return whether generic workflow regex would steal a patch phrase."""
    normalized = _normalize(_prepare_text(text))
    if is_patch_workflow_phrase(normalized):
        return False, ""
    match = _GENERIC_WORKFLOW_CAPTURE.search(normalized)
    if not match:
        return False, ""
    wf_name = (match.group(1) or match.group(2) or "").strip().lower()
    return bool(wf_name), wf_name


def validate_patch_workflow_phrase_collisions() -> list[str]:
    """Detect patch phrases that would classify as generic run_workflow."""
    issues: list[str] = []
    for phrase in PATCH_PROTECTED_PHRASES:
        req = match_patch_workflow_commands(phrase)
        if req is None:
            issues.append(f"patch phrase {phrase!r} has no patch matcher")
            continue
        if req.intent == Intent.RUN_WORKFLOW:
            issues.append(f"patch phrase {phrase!r} maps to run_workflow")
            continue
        captured, wf_name = generic_workflow_would_capture(phrase)
        if captured and req.intent == Intent.RUN_WORKFLOW:
            issues.append(
                f"patch phrase {phrase!r} collides with generic workflow capture {wf_name!r}"
            )
        rules_intent = req.intent.value
        if phrase in {"show patch workflow status", "run patch workflow confirm"}:
            if rules_intent not in {
                Intent.SHOW_PATCH_WORKFLOW_STATUS.value,
                Intent.RUN_PATCH_WORKFLOW.value,
            }:
                issues.append(
                    f"patch phrase {phrase!r} expected patch workflow intent, got {rules_intent}"
                )
    return issues
