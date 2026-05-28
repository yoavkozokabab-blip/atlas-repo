"""Emotional prosody layer for conversational speech (Phase 59)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voice.providers.base import SpeechProsody
from voice.realtime_tts import apply_prosody


@dataclass(frozen=True)
class SpeechStyle:
    emotion: str
    speed: float
    urgency: str = "normal"
    confidence: str = "normal"
    label: str = "neutral"


_STYLE_MAP: dict[str, SpeechStyle] = {
    "urgent": SpeechStyle(emotion="urgent", speed=1.15, urgency="high", label="urgent"),
    "confident": SpeechStyle(emotion="confident", speed=1.05, confidence="high", label="confident"),
    "humor": SpeechStyle(emotion="warm", speed=1.08, label="humor"),
    "warning": SpeechStyle(emotion="concerned", speed=0.95, urgency="high", label="warning"),
    "investigation_critical": SpeechStyle(
        emotion="serious",
        speed=0.92,
        urgency="high",
        label="investigation_critical",
    ),
    "investigation_moderate": SpeechStyle(
        emotion="thoughtful",
        speed=0.98,
        label="investigation_moderate",
    ),
    "neutral": SpeechStyle(emotion="neutral", speed=1.0, label="neutral"),
    "positive": SpeechStyle(emotion="warm", speed=1.02, label="positive"),
    "frustrated": SpeechStyle(emotion="calm", speed=0.9, label="empathetic"),
}


def infer_speech_style(
    *,
    text: str = "",
    intent: str = "",
    status: str = "success",
    emotional_tone: str = "neutral",
    investigation_severity: str = "",
) -> SpeechStyle:
    lower = (text or "").lower()
    intent_l = (intent or "").lower()
    if investigation_severity in {"critical", "high", "severe"}:
        return _STYLE_MAP["investigation_critical"]
    if investigation_severity in {"moderate", "medium"}:
        return _STYLE_MAP["investigation_moderate"]
    if any(x in lower for x in ("urgent", "immediately", "asap", "critical", "down")):
        return _STYLE_MAP["urgent"]
    if any(x in lower for x in ("warning", "careful", "blocked", "failed", "error")):
        return _STYLE_MAP["warning"]
    if any(x in lower for x in ("haha", "funny", "joke", "lol")):
        return _STYLE_MAP["humor"]
    if status != "success" or "fail" in intent_l:
        return _STYLE_MAP["warning"]
    if emotional_tone == "frustrated":
        return _STYLE_MAP["frustrated"]
    if emotional_tone == "positive":
        return _STYLE_MAP["positive"]
    if any(x in lower for x in ("sure", "confirmed", "done", "completed")):
        return _STYLE_MAP["confident"]
    return _STYLE_MAP["neutral"]


def build_prosody(style: SpeechStyle) -> SpeechProsody:
    return apply_prosody("", emotion=style.emotion, speed=style.speed)


def describe_speech_style(style: SpeechStyle) -> str:
    return (
        f"emotion={style.emotion} speed={style.speed:.2f} "
        f"urgency={style.urgency} confidence={style.confidence} label={style.label}"
    )


def infer_from_conversation_context(context: dict[str, Any] | None = None) -> SpeechStyle:
    ctx = context or {}
    return infer_speech_style(
        text=str(ctx.get("last_user_text") or ctx.get("text") or ""),
        intent=str(ctx.get("last_intent") or ctx.get("intent") or ""),
        status=str(ctx.get("status") or "success"),
        emotional_tone=str(ctx.get("emotional_tone") or "neutral"),
        investigation_severity=str(ctx.get("investigation_severity") or ""),
    )
