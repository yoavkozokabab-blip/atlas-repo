"""Voice command safety guard — block ambiguous short STT transcripts (Phase 57)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.logger import setup_logger
from core.results import result_blocked, result_clarification, result_confirmation_required
from core.types import CommandRequest, CommandResult, Intent

logger = setup_logger("jarvis.voice.command_guard")

_FILLER_TRANSCRIPTS = frozenset(
    {
        "oh",
        "uh",
        "um",
        "hmm",
        "hm",
        "ah",
        "eh",
        "oops",
        "sorry",
        "ok",
        "okay",
        "yeah",
        "yep",
        "nope",
        "huh",
        "well",
        "like",
        "so",
    }
)

_AMBIGUOUS_FRAGMENTS = frozenset(
    {
        "open",
        "close",
        "do",
        "it",
        "go",
        "run",
        "stop",
        "start",
        "yes",
        "no",
        "delete",
        "send",
        "apply",
        "execute",
    }
)

_COMMAND_VERBS = frozenset(
    {
        "open",
        "close",
        "start",
        "stop",
        "run",
        "show",
        "delete",
        "remove",
        "apply",
        "execute",
        "send",
        "search",
        "find",
        "describe",
        "analyze",
        "switch",
        "focus",
        "test",
        "launch",
        "bring",
        "tell",
        "explain",
        "summarize",
        "list",
        "check",
        "confirm",
        "cancel",
        "play",
        "read",
        "inspect",
        "propose",
        "simulate",
        "validate",
        "review",
        "continue",
        "resume",
    }
)

_READ_ONLY_INTENTS = frozenset(
    {
        Intent.SHOW_VOICE_LATENCY.value,
        Intent.PHASE57_STATUS.value,
        Intent.TEST_REALTIME_VOICE.value,
        Intent.TEST_INTERRUPT_SPEECH.value,
        Intent.SHOW_AUDIO_STATUS.value,
        Intent.SHOW_TTS_STATUS.value,
        Intent.SHOW_TTS_DEBUG.value,
        Intent.TEST_TTS_PLAYBACK.value,
        Intent.TEST_DIRECT_TTS.value,
        Intent.TEST_STREAMING_STT.value,
        Intent.SHOW_STT_STATUS.value,
        Intent.SHOW_CAPABILITIES.value,
        Intent.SHOW_JARVIS_STATUS.value,
        Intent.UNKNOWN.value,
        Intent.CLARIFY.value,
    }
)


def is_voice_command_guard_enabled() -> bool:
    try:
        import config as cfg

        if getattr(cfg, "VOICE_RUNTIME_STABLE", False):
            return False
        return bool(getattr(cfg, "VOICE_COMMAND_GUARD_ENABLED", True))
    except Exception:
        return True


def voice_risky_intents() -> frozenset[str]:
    try:
        import config as cfg

        return getattr(cfg, "VOICE_RISKY_INTENTS", frozenset())
    except Exception:
        return frozenset()


def voice_confirmation_intents() -> frozenset[str]:
    try:
        import config as cfg
        from config import CONFIRMATION_REQUIRED_INTENTS

        extra = getattr(cfg, "VOICE_CONFIRMATION_INTENTS", frozenset())
        return frozenset(CONFIRMATION_REQUIRED_INTENTS) | frozenset(extra)
    except Exception:
        return frozenset()


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


def word_count(text: str) -> int:
    normalized = _normalize(text)
    return len(normalized.split()) if normalized else 0


def is_filler_transcript(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return True
    if normalized in _FILLER_TRANSCRIPTS:
        return True
    words = normalized.split()
    return len(words) == 1 and words[0] in _FILLER_TRANSCRIPTS


def has_command_verb(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    words = normalized.split()
    if words and words[0] in _COMMAND_VERBS:
        return True
    return any(word in _COMMAND_VERBS for word in words)


def has_explicit_target(text: str, request: CommandRequest) -> bool:
    normalized = _normalize(text)
    words = normalized.split()
    if len(words) >= 2 and has_command_verb(text):
        return True
    if request.params:
        return True
    if request.intent.value.startswith("show_") or request.intent.value.startswith("list_"):
        return len(words) >= 2
    return False


def is_ambiguous_short_voice_command(text: str, request: CommandRequest) -> bool:
    """True when a short voice transcript should not execute an action."""
    if request.confirmed:
        return False
    if request.intent.value in _READ_ONLY_INTENTS:
        return False

    normalized = _normalize(text)
    if not normalized:
        return True
    if is_filler_transcript(text):
        return True

    words = word_count(text)
    min_words = 3
    try:
        import config as cfg

        min_words = int(getattr(cfg, "VOICE_GUARD_MIN_WORDS", 3))
    except Exception:
        pass

    if normalized in _AMBIGUOUS_FRAGMENTS:
        return True

    if words < min_words:
        if has_explicit_target(text, request):
            return False
        if has_command_verb(text) and request.confidence >= 0.9 and words == 2:
            return False
        return True

    try:
        import config as cfg
        from config import CONFIDENCE_THRESHOLD

        threshold = float(getattr(cfg, "VOICE_GUARD_MIN_CONFIDENCE", CONFIDENCE_THRESHOLD))
    except Exception:
        threshold = 0.65

    if request.confidence < threshold and not has_command_verb(text):
        return True

    if not has_command_verb(text) and request.intent not in (Intent.UNKNOWN, Intent.CLARIFY):
        if words < min_words + 1:
            return True

    return False


@dataclass(frozen=True)
class VoiceGuardDecision:
    blocked: bool
    reason: str = ""
    requires_confirmation: bool = False
    confirmation_message: str = ""


def evaluate_voice_command(
    request: CommandRequest,
    *,
    input_mode: str,
) -> VoiceGuardDecision | None:
    """Return a guard decision for voice/wakeword input, or None to proceed."""
    if input_mode not in ("voice", "wakeword"):
        return None
    if not is_voice_command_guard_enabled():
        return None
    if request.confirmed:
        return None

    text = request.raw_text
    intent_val = request.intent.value

    if is_filler_transcript(text):
        return VoiceGuardDecision(blocked=True, reason="filler_transcript")

    if is_ambiguous_short_voice_command(text, request):
        return VoiceGuardDecision(blocked=True, reason="ambiguous_short_transcript")

    risky = voice_risky_intents()
    confirm_intents = voice_confirmation_intents()
    if intent_val in confirm_intents or intent_val in risky:
        label = intent_val.replace("_", " ")
        target = ""
        if request.params:
            bits = [f"{k}={v}" for k, v in list(request.params.items())[:2]]
            target = f" ({', '.join(bits)})" if bits else ""
        return VoiceGuardDecision(
            blocked=False,
            requires_confirmation=True,
            confirmation_message=f"Did you mean {label}{target}?",
        )

    return None


def apply_voice_command_guard(
    request: CommandRequest,
    *,
    input_mode: str,
) -> CommandResult | None:
    """Apply guard policy; return CommandResult when execution must stop."""
    decision = evaluate_voice_command(request, input_mode=input_mode)
    if decision is None:
        return None

    if decision.blocked:
        logger.info(
            "voice guard blocked intent=%s reason=%s text=%r",
            request.intent.value,
            decision.reason,
            request.raw_text[:40],
        )
        if decision.reason == "filler_transcript":
            return result_blocked(
                request.intent,
                "I didn't catch a command — still listening.",
            )
        return result_clarification(
            request.intent,
            "I didn't catch a clear command. Please say what you'd like me to do.",
        )

    if decision.requires_confirmation and not request.confirmed:
        from core import confirmation

        cid = confirmation.create_confirmation(
            request.intent.value,
            {
                "raw_text": request.raw_text,
                "params": request.params,
            },
        )
        msg = decision.confirmation_message or (
            f"'{request.intent.value}' requires confirmation. Reply yes/confirm or no/cancel."
        )
        return result_confirmation_required(request.intent, f"{msg} (id: {cid})", cid)

    return None


def show_voice_guard_status() -> str:
    risky = sorted(voice_risky_intents())
    confirm = sorted(voice_confirmation_intents())
    lines = [
        "Voice command safety guard (Phase 57):",
        f"  enabled: {'yes' if is_voice_command_guard_enabled() else 'no'}",
        f"  risky intents: {len(risky)}",
        f"  confirmation intents: {len(confirm)}",
    ]
    if risky:
        lines.append(f"  risky sample: {', '.join(risky[:8])}")
    return "\n".join(lines)
