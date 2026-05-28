"""In-memory voice/STT debug trace (display-only, no secrets)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock

from voice.stt_diagnostics import snapshot as stt_diag_snapshot

_lock = Lock()
_last_raw: str = ""
_last_normalized: str = ""
_last_grammar_corrected: str = ""
_last_grammar_command: str = ""
_last_grammar_confidence: float = 0.0
_last_grammar_reason: str = ""
_last_retry_reason: str = ""
_last_pass_latencies: dict[str, float] = {}
_last_confidence_logprob: float | None = None
_last_low_confidence: bool = False
_last_transcript_at: str | None = None
_failed_transcripts: list[str] = []
_corrected_transcripts: list[str] = []
_last_semantic_intent: str = ""
_last_semantic_confidence: float = 0.0
_last_semantic_canonical: str = ""
_last_semantic_reason: str = ""
_last_semantic_ambiguous: bool = False
_last_semantic_clarification: str = ""
_last_semantic_llm_used: bool = False
_last_final_routed_intent: str = ""


@dataclass
class VoiceDebugSnapshot:
    last_raw_transcript: str = ""
    last_normalized_transcript: str = ""
    last_grammar_corrected_transcript: str = ""
    last_grammar_command: str = ""
    last_grammar_confidence: float = 0.0
    last_grammar_correction_reason: str = ""
    last_retry_reason: str = ""
    last_pass_latencies_ms: dict[str, float] = field(default_factory=dict)
    last_avg_logprob: float | None = None
    last_transcript_at: str | None = None
    last_low_confidence: bool = False
    wake_retries: int = 0
    low_confidence_count: int = 0
    empty_transcript_count: int = 0
    consecutive_empty_wake: int = 0
    wake_phrase_detected_count: int = 0
    stt_model: str = ""
    stt_backend: str = ""
    stt_device: str = ""
    stt_beam_size: int = 0
    failed_transcripts: tuple[str, ...] = ()
    corrected_transcripts: tuple[str, ...] = ()
    semantic_candidate_intent: str = ""
    semantic_confidence: float = 0.0
    semantic_canonical_command: str = ""
    semantic_ambiguity_reason: str = ""
    semantic_clarification: str = ""
    semantic_llm_used: bool = False
    final_routed_intent: str = ""


def record_semantic_debug(sem: object) -> None:
    """Record semantic layer snapshot for show voice debug."""
    global _last_semantic_intent, _last_semantic_confidence, _last_semantic_canonical
    global _last_semantic_reason, _last_semantic_ambiguous, _last_semantic_clarification
    global _last_semantic_llm_used, _last_final_routed_intent
    with _lock:
        _last_semantic_intent = str(getattr(sem, "candidate_intent", "") or "")[:120]
        _last_semantic_confidence = float(getattr(sem, "confidence", 0.0) or 0.0)
        _last_semantic_canonical = str(getattr(sem, "canonical_command", "") or "")[:200]
        _last_semantic_reason = str(getattr(sem, "reasoning", "") or "")[:200]
        _last_semantic_ambiguous = bool(getattr(sem, "ambiguous", False))
        _last_semantic_clarification = str(getattr(sem, "clarification", "") or "")[:300]
        _last_semantic_llm_used = bool(getattr(sem, "llm_used", False))
        _last_final_routed_intent = str(
            getattr(sem, "final_routed_intent", "") or getattr(sem, "candidate_intent", "") or ""
        )[:120]


def record_transcript_debug(
    *,
    raw: str,
    normalized: str,
    avg_logprob: float | None = None,
    low_confidence: bool = False,
) -> None:
    record_voice_understanding(
        raw=raw,
        normalized=normalized,
        grammar_corrected=normalized,
        grammar_command="",
        grammar_confidence=0.0,
        grammar_reason="",
        retry_reason="",
        pass_latencies_ms={},
        avg_logprob=avg_logprob,
        low_confidence=low_confidence,
    )


def record_voice_understanding(
    *,
    raw: str,
    normalized: str,
    grammar_corrected: str,
    grammar_command: str = "",
    grammar_confidence: float = 0.0,
    grammar_reason: str = "",
    retry_reason: str = "",
    pass_latencies_ms: dict[str, float] | None = None,
    avg_logprob: float | None = None,
    low_confidence: bool = False,
) -> None:
    global _last_raw, _last_normalized, _last_grammar_corrected
    global _last_grammar_command, _last_grammar_confidence, _last_grammar_reason
    global _last_retry_reason, _last_pass_latencies
    global _last_confidence_logprob, _last_low_confidence, _last_transcript_at
    with _lock:
        _last_raw = (raw or "")[:500]
        _last_normalized = (normalized or "")[:500]
        _last_grammar_corrected = (grammar_corrected or normalized or raw or "")[:500]
        _last_grammar_command = (grammar_command or "")[:120]
        _last_grammar_confidence = float(grammar_confidence or 0.0)
        _last_grammar_reason = (grammar_reason or "")[:120]
        _last_retry_reason = (retry_reason or "")[:120]
        _last_pass_latencies = dict(pass_latencies_ms or {})
        _last_confidence_logprob = avg_logprob
        _last_low_confidence = low_confidence
        _last_transcript_at = datetime.now(timezone.utc).isoformat()
        if low_confidence or not (_last_grammar_corrected or "").strip():
            entry = (_last_raw or _last_normalized or "(empty)")[:160]
            _failed_transcripts.append(entry)
            del _failed_transcripts[:-10]
        if (
            grammar_reason
            and _last_grammar_corrected
            and _last_grammar_corrected.lower() != (_last_raw or "").lower()
        ):
            _corrected_transcripts.append(
                f"{(_last_raw or '')[:80]!r} -> {_last_grammar_corrected[:80]!r}"
            )
            del _corrected_transcripts[:-10]


def get_voice_debug_snapshot() -> VoiceDebugSnapshot:
    diag = stt_diag_snapshot()
    try:
        import config
        from core.runtime_state import get_runtime_state
        from voice.transcriber import get_stt_status

        stt = get_stt_status()
        wake_count = get_runtime_state().wake_word_detection_count
        beam = int(config.STT_BEAM_SIZE)
        model = stt.model
        backend = stt.backend
        device = stt.device
    except Exception:
        wake_count = 0
        beam = 0
        model = diag.last_model
        backend = ""
        device = ""
    with _lock:
        return VoiceDebugSnapshot(
            last_raw_transcript=_last_raw,
            last_normalized_transcript=_last_normalized,
            last_grammar_corrected_transcript=_last_grammar_corrected,
            last_grammar_command=_last_grammar_command,
            last_grammar_confidence=_last_grammar_confidence,
            last_grammar_correction_reason=_last_grammar_reason,
            last_retry_reason=_last_retry_reason,
            last_pass_latencies_ms=dict(_last_pass_latencies),
            last_avg_logprob=_last_confidence_logprob,
            last_transcript_at=_last_transcript_at,
            last_low_confidence=_last_low_confidence,
            wake_retries=diag.wake_retry_count,
            low_confidence_count=diag.low_confidence_count,
            empty_transcript_count=diag.empty_transcript_count,
            consecutive_empty_wake=diag.consecutive_empty_wake,
            wake_phrase_detected_count=wake_count,
            stt_model=model,
            stt_backend=backend,
            stt_device=device,
            stt_beam_size=beam,
            failed_transcripts=tuple(_failed_transcripts[-10:]),
            corrected_transcripts=tuple(_corrected_transcripts[-10:]),
            semantic_candidate_intent=_last_semantic_intent,
            semantic_confidence=_last_semantic_confidence,
            semantic_canonical_command=_last_semantic_canonical,
            semantic_ambiguity_reason=_last_semantic_reason,
            semantic_clarification=_last_semantic_clarification,
            semantic_llm_used=_last_semantic_llm_used,
            final_routed_intent=_last_final_routed_intent,
        )


def format_voice_debug_status() -> str:
    s = get_voice_debug_snapshot()
    lines = [
        "Voice debug",
        f"  raw_transcript: {s.last_raw_transcript!r}" if s.last_raw_transcript else "  raw_transcript: (none)",
        f"  normalized_transcript: {s.last_normalized_transcript!r}"
        if s.last_normalized_transcript
        else "  normalized_transcript: (none)",
        f"  grammar_corrected_transcript: {s.last_grammar_corrected_transcript!r}"
        if s.last_grammar_corrected_transcript
        else "  grammar_corrected_transcript: (none)",
        f"  selected_command: {s.last_grammar_command or 'n/a'}",
        f"  grammar_confidence: {s.last_grammar_confidence:.3f}"
        if s.last_grammar_confidence
        else "  grammar_confidence: n/a",
        f"  correction_reason: {s.last_grammar_correction_reason or 'n/a'}",
        f"  retry_reason: {s.last_retry_reason or 'n/a'}",
        f"  semantic_candidate: {s.semantic_candidate_intent or 'n/a'}",
        f"  semantic_confidence: {s.semantic_confidence:.3f}"
        if s.semantic_confidence
        else "  semantic_confidence: n/a",
        f"  semantic_canonical: {s.semantic_canonical_command or 'n/a'}",
        f"  semantic_ambiguity_reason: {s.semantic_ambiguity_reason or 'n/a'}",
        f"  semantic_clarification: {s.semantic_clarification or 'n/a'}",
        f"  semantic_llm_used: {'yes' if s.semantic_llm_used else 'no'}",
        f"  final_routed_intent: {s.final_routed_intent or 'n/a'}",
    ]
    if s.last_pass_latencies_ms:
        lines.append("  stt_latency_by_pass_ms:")
        for name, ms in sorted(s.last_pass_latencies_ms.items()):
            lines.append(f"    {name}: {ms:.0f}")
    lines.extend(
        [
            f"  last_avg_logprob: {s.last_avg_logprob:.3f}"
            if s.last_avg_logprob is not None
            else "  last_avg_logprob: n/a",
            f"  last_transcript_at: {s.last_transcript_at or 'n/a'}",
            f"  last_low_confidence: {'yes' if s.last_low_confidence else 'no'}",
            f"  stt_model: {s.stt_model or 'n/a'}",
            f"  stt_backend: {s.stt_backend or 'n/a'}",
            f"  stt_device: {s.stt_device or 'n/a'}",
            f"  stt_beam_size: {s.stt_beam_size or 'n/a'}",
            f"  wake_retries: {s.wake_retries}",
            f"  wake_phrase_detected_count: {s.wake_phrase_detected_count}",
            f"  low_confidence_count: {s.low_confidence_count}",
            f"  empty_transcript_count: {s.empty_transcript_count}",
            f"  consecutive_empty_wake: {s.consecutive_empty_wake}",
        ]
    )
    if s.failed_transcripts:
        lines.append("  last_failed_phrases:")
        for item in s.failed_transcripts:
            lines.append(f"    - {item!r}")
    if s.corrected_transcripts:
        lines.append("  last_corrected_phrases:")
        for item in s.corrected_transcripts:
            lines.append(f"    - {item}")
    return "\n".join(lines)


def reset_voice_debug_store() -> None:
    global _last_raw, _last_normalized, _last_grammar_corrected
    global _last_grammar_command, _last_grammar_confidence, _last_grammar_reason
    global _last_retry_reason, _last_pass_latencies
    global _last_confidence_logprob, _last_low_confidence, _last_transcript_at
    global _last_semantic_intent, _last_semantic_confidence, _last_semantic_canonical
    global _last_semantic_reason, _last_semantic_ambiguous, _last_semantic_clarification
    global _last_semantic_llm_used, _last_final_routed_intent
    with _lock:
        _last_raw = ""
        _last_normalized = ""
        _last_grammar_corrected = ""
        _last_grammar_command = ""
        _last_grammar_confidence = 0.0
        _last_grammar_reason = ""
        _last_retry_reason = ""
        _last_pass_latencies = {}
        _last_confidence_logprob = None
        _last_low_confidence = False
        _last_transcript_at = None
        _failed_transcripts.clear()
        _corrected_transcripts.clear()
        _last_semantic_intent = ""
        _last_semantic_confidence = 0.0
        _last_semantic_canonical = ""
        _last_semantic_reason = ""
        _last_semantic_ambiguous = False
        _last_semantic_clarification = ""
        _last_semantic_llm_used = False
        _last_final_routed_intent = ""
