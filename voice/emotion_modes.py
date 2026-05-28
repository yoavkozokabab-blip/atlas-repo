"""Phase 41 — voice emotion / style presets (rate + voice hints)."""

from __future__ import annotations

from dataclasses import dataclass

VALID_EMOTIONS = frozenset({"calm", "assistant", "alert", "focused", "cinematic"})


@dataclass(frozen=True)
class EmotionPreset:
    name: str
    rate_raw: str
    edge_voice: str
    description: str


# Female-forward cinematic default: Jenny / Aria neural voices on edge-tts.
EMOTION_PRESETS: dict[str, EmotionPreset] = {
    "calm": EmotionPreset(
        "calm",
        "-5%",
        "en-US-JennyNeural",
        "Soft, steady delivery for long explanations.",
    ),
    "assistant": EmotionPreset(
        "assistant",
        "+0%",
        "en-US-JennyNeural",
        "Clear neutral assistant (default female neural).",
    ),
    "alert": EmotionPreset(
        "alert",
        "+12%",
        "en-US-AriaNeural",
        "Faster, brighter tone for errors and warnings.",
    ),
    "focused": EmotionPreset(
        "focused",
        "+5%",
        "en-US-JennyNeural",
        "Crisp and efficient for task execution.",
    ),
    "cinematic": EmotionPreset(
        "cinematic",
        "+8%",
        "en-US-AriaNeural",
        "Premium cinematic presence (Iron Man style).",
    ),
}


def get_emotion_preset(name: str) -> EmotionPreset | None:
    key = (name or "").strip().lower()
    return EMOTION_PRESETS.get(key)


def format_emotion_catalog() -> str:
    lines = ["Voice emotion modes:"]
    for key, preset in EMOTION_PRESETS.items():
        lines.append(f"  {key}: {preset.description}")
        lines.append(f"    voice={preset.edge_voice} rate={preset.rate_raw}")
    lines.append("Say: set voice emotion calm | assistant | alert | focused | cinematic")
    return "\n".join(lines)
