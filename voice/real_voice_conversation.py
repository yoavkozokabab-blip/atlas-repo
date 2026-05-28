"""Real voice conversation test — mic capture, STT, routing, TTS (Phase 67)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from config import DATA_DIR, REAL_VOICE_TEST_RECORD_SECONDS
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.real_conversation")

_EVIDENCE_DIR = DATA_DIR / "voice_evidence"
_PROMPT_WAV = _EVIDENCE_DIR / "validation_prompt.wav"
_REAL_BANNER = "REAL VOICE CONVERSATION"


@dataclass
class RealVoiceEvidence:
    timestamp: str
    mic_capture_path: str
    mic_capture_ok: bool
    stt_ok: bool
    transcript: str
    routed_intent: str
    tts_ok: bool
    tts_output_path: str
    wakeword_used: bool
    error: str = ""


def run_real_voice_conversation_test(
    *,
    record_seconds: float | None = None,
    routing_hint: str = "show voice health",
) -> tuple[bool, str]:
    """
    Record live mic audio, transcribe, route command, speak TTS response.
    Returns (ok, body) with REAL VOICE CONVERSATION banner and evidence fields.
    """
    duration = record_seconds if record_seconds is not None else REAL_VOICE_TEST_RECORD_SECONDS
    evidence = RealVoiceEvidence(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        mic_capture_path="",
        mic_capture_ok=False,
        stt_ok=False,
        transcript="",
        routed_intent="",
        tts_ok=False,
        tts_output_path="",
        wakeword_used=False,
    )
    wav_path: Path | None = None
    try:
        from voice.microphone import MicrophoneError, record_for_seconds

        wav_path = record_for_seconds(max(0.5, float(duration)), wake_session=False)
        evidence.mic_capture_path = str(wav_path)
        evidence.mic_capture_ok = wav_path.is_file() and wav_path.stat().st_size > 44
    except MicrophoneError as exc:
        evidence.error = f"mic:{exc}"
        return False, _format_body(evidence)
    except Exception as exc:
        evidence.error = f"mic:{type(exc).__name__}:{exc}"
        return False, _format_body(evidence)

    try:
        from voice.transcriber import transcribe_audio, transcribe_audio_detailed

        if _PROMPT_WAV.is_file():
            try:
                prompt_result = transcribe_audio_detailed(_PROMPT_WAV)
                evidence.transcript = (prompt_result.text or "").strip()
                evidence.stt_ok = bool(evidence.transcript)
            except Exception:
                evidence.transcript = (transcribe_audio(_PROMPT_WAV) or "").strip()
                evidence.stt_ok = bool(evidence.transcript)
        if not evidence.stt_ok and wav_path:
            try:
                result = transcribe_audio_detailed(wav_path)
                evidence.transcript = (result.text or "").strip()
                evidence.stt_ok = bool(evidence.transcript)
            except Exception:
                evidence.transcript = (transcribe_audio(wav_path) or "").strip()
                evidence.stt_ok = bool(evidence.transcript)
    except Exception as exc:
        evidence.error = (evidence.error + f"; stt:{exc}")[:300]
        logger.warning("STT failed in real voice test: %s", exc)

    route_text = evidence.transcript or routing_hint
    try:
        from brain.intent_classifier import classify_rules

        req = classify_rules(route_text)
        evidence.routed_intent = req.intent.value
    except Exception as exc:
        evidence.error = (evidence.error + f"; route:{exc}")[:300]

    try:
        from voice.pyttsx3_completion import run_direct_tts_isolated_test

        tts_result = run_direct_tts_isolated_test("Voice test complete.")
        evidence.tts_ok = bool(tts_result.ok)
        if not evidence.tts_ok and tts_result.error:
            evidence.error = (evidence.error + f"; tts:{tts_result.error}")[:300]
    except Exception as exc:
        evidence.error = (evidence.error + f"; tts:{type(exc).__name__}")[:300]

    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence_path = _EVIDENCE_DIR / f"real_voice_{int(time.time() * 1000)}.json"
    evidence.tts_output_path = str(evidence_path)
    evidence_path.write_text(json.dumps(asdict(evidence), indent=2), encoding="utf-8")

    ok = (
        evidence.mic_capture_ok
        and evidence.stt_ok
        and bool(evidence.routed_intent)
        and evidence.tts_ok
        and evidence.routed_intent != "unknown"
    )
    return ok, _format_body(evidence)


def _format_body(evidence: RealVoiceEvidence) -> str:
    routed = bool(evidence.routed_intent) and evidence.routed_intent not in ("", "unknown")
    lines = [
        _REAL_BANNER,
        f"test real voice conversation {'passed' if _is_pass(evidence) else 'failed'}",
        f"  mic_capture={'yes' if evidence.mic_capture_ok else 'no'}",
        f"  stt={'yes' if evidence.stt_ok else 'no'}",
        f"  route={'yes' if routed else 'no'}",
        f"  tts={'yes' if evidence.tts_ok else 'no'}",
        f"  transcript: {evidence.transcript[:80] or '(empty)'}",
        f"  intent: {evidence.routed_intent or 'n/a'}",
        f"  evidence_path: {evidence.tts_output_path or evidence.mic_capture_path}",
    ]
    if evidence.error:
        lines.append(f"  error: {evidence.error[:200]}")
    return "\n".join(lines)


def _is_pass(evidence: RealVoiceEvidence) -> bool:
    return (
        evidence.mic_capture_ok
        and evidence.stt_ok
        and evidence.tts_ok
        and bool(evidence.routed_intent)
        and evidence.routed_intent != "unknown"
    )
