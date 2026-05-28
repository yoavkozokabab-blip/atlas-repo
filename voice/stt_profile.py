"""Voice/STT profile overrides (fast vs accurate, local only)."""

from __future__ import annotations

from dataclasses import dataclass

FAST_MODELS = frozenset({"tiny", "base", "small"})
SLOW_MODELS = frozenset({"medium", "large", "large-v2", "large-v3", "distil-large-v3"})


@dataclass
class SttProfileOverrides:
    model: str
    beam_size: int
    wake_max_listen_seconds: float
    fast_voice_mode: bool
    low_confidence_block_wake: bool | None
    applied: bool
    profile_name: str


def apply_voice_profile(
    *,
    voice_profile: str,
    stt_fast_profile: bool,
    fast_voice_mode: bool,
    model_raw: str,
    beam_size: int,
    wake_max_listen_seconds: float,
    low_confidence_block_wake_env: bool,
) -> SttProfileOverrides:
    profile = (voice_profile or "").strip().lower()

    if profile == "accurate":
        model = model_raw.strip().lower()
        if model not in SLOW_MODELS:
            model = "medium"
        return SttProfileOverrides(
            model=model,
            beam_size=max(3, beam_size) if beam_size >= 3 else 3,
            wake_max_listen_seconds=max(float(wake_max_listen_seconds), 5.0),
            fast_voice_mode=fast_voice_mode,
            low_confidence_block_wake=True,
            applied=True,
            profile_name="accurate",
        )

    if profile in {"", "balanced"}:
        return SttProfileOverrides(
            model="small",
            beam_size=max(3, int(beam_size)),
            wake_max_listen_seconds=max(float(wake_max_listen_seconds), 5.0),
            fast_voice_mode=False,
            low_confidence_block_wake=False,
            applied=True,
            profile_name="balanced",
        )

    fast = stt_fast_profile or profile == "fast" or fast_voice_mode
    if not fast:
        return SttProfileOverrides(
            model=model_raw,
            beam_size=beam_size,
            wake_max_listen_seconds=wake_max_listen_seconds,
            fast_voice_mode=fast_voice_mode,
            low_confidence_block_wake=None,
            applied=False,
            profile_name=profile or "default",
        )

    model = model_raw.strip().lower()
    if model in SLOW_MODELS or model not in FAST_MODELS:
        model = "small"

    beam = max(1, min(int(beam_size), 2))
    wake_cap = min(float(wake_max_listen_seconds), 4.0)
    block_wake = False if profile == "fast" or stt_fast_profile else low_confidence_block_wake_env

    return SttProfileOverrides(
        model=model,
        beam_size=beam,
        wake_max_listen_seconds=wake_cap,
        fast_voice_mode=True,
        low_confidence_block_wake=block_wake,
        applied=True,
        profile_name="fast" if profile == "fast" or stt_fast_profile else "fast_voice",
    )
