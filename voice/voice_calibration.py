"""Local voice calibration v2 (safe, deterministic, no cloud)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import VOICE_CALIBRATION_ENABLED, VOICE_CALIBRATION_MAX_SAMPLES, VOICE_CALIBRATION_PATH
from voice.spoken_normalization import normalize_spoken_command
from voice.transcript_cleanup import cleanup_transcript
from vision.redaction import redact_sensitive_text

CALIBRATION_PROMPTS: tuple[str, ...] = (
    "show jarvis status",
    "open dashboard",
    "show audio status",
    "test voice output",
    "show voice debug",
    "describe screen",
    "what am i doing",
    "run diagnostics",
    "show wake diagnostics",
    "open tradingview",
)

_SECRET_MARKERS = ("[redacted]", "password", "secret", "token", "api_key", "apikey", "bearer")


@dataclass(frozen=True)
class CalibrationSample:
    expected_phrase: str
    heard_transcript: str
    normalized_transcript: str


@dataclass(frozen=True)
class CalibrationResult:
    path: Path
    samples: tuple[CalibrationSample, ...]
    recommended_profile: str
    correction_pairs: tuple[tuple[str, str], ...]


def _safe_text(text: str) -> str:
    redacted = redact_sensitive_text(text or "").strip()
    lowered = redacted.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return ""
    return redacted[:240]


def _normalize(text: str) -> str:
    return normalize_spoken_command(cleanup_transcript(text or ""))[:240]


def _load_payload() -> dict:
    path = Path(VOICE_CALIBRATION_PATH)
    if not path.is_file():
        return {"samples": [], "correction_pairs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"samples": [], "correction_pairs": []}
    except (OSError, json.JSONDecodeError):
        return {"samples": [], "correction_pairs": []}


def _save_payload(data: dict) -> Path:
    path = Path(VOICE_CALIBRATION_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def suggest_voice_profile(samples: tuple[CalibrationSample, ...]) -> str:
    if not samples:
        return "balanced"
    heard_nonempty = sum(1 for s in samples if s.heard_transcript.strip())
    if heard_nonempty == 0:
        return "balanced"
    exact = sum(
        1
        for item in samples
        if item.heard_transcript
        and item.expected_phrase.lower() == item.normalized_transcript.lower()
    )
    ratio = exact / max(1, heard_nonempty)
    if ratio >= 0.85:
        return "fast"
    if ratio >= 0.55:
        return "balanced"
    return "accurate"


def run_voice_calibration(
    samples: list[str] | tuple[str, ...] | None = None,
) -> CalibrationResult:
    """Prepare calibration session — user should speak each expected phrase via voice."""
    if not VOICE_CALIBRATION_ENABLED:
        prompts = tuple(samples or CALIBRATION_PROMPTS)[:VOICE_CALIBRATION_MAX_SAMPLES]
        empty = tuple(
            CalibrationSample(expected_phrase=p, heard_transcript="", normalized_transcript="")
            for p in prompts
            if _safe_text(p)
        )
        return CalibrationResult(
            path=Path(VOICE_CALIBRATION_PATH),
            samples=empty,
            recommended_profile="balanced",
            correction_pairs=(),
        )

    raw_samples = tuple(samples or CALIBRATION_PROMPTS)[:VOICE_CALIBRATION_MAX_SAMPLES]
    safe_samples: list[CalibrationSample] = []
    for expected in raw_samples:
        safe_expected = _safe_text(expected)
        if not safe_expected:
            continue
        safe_samples.append(
            CalibrationSample(
                expected_phrase=safe_expected,
                heard_transcript="",
                normalized_transcript=_normalize(safe_expected),
            )
        )

    data = _load_payload()
    path = _save_payload(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "recommended_profile": suggest_voice_profile(tuple(safe_samples)),
            "pending": True,
            "samples": [
                {
                    "expected_phrase": s.expected_phrase,
                    "heard_transcript": s.heard_transcript,
                    "normalized_transcript": s.normalized_transcript,
                }
                for s in safe_samples
            ],
            "correction_pairs": list(data.get("correction_pairs") or [])[:VOICE_CALIBRATION_MAX_SAMPLES],
        }
    )
    pairs = tuple(
        (str(a), str(b))
        for a, b in (data.get("correction_pairs") or [])
        if isinstance(a, str) and isinstance(b, str)
    )[:VOICE_CALIBRATION_MAX_SAMPLES]
    result = CalibrationResult(
        path=path,
        samples=tuple(safe_samples),
        recommended_profile=suggest_voice_profile(tuple(safe_samples)),
        correction_pairs=pairs,
    )
    try:
        from voice.voice_stack_store import load_voice_profile, save_voice_profile

        prof = load_voice_profile()
        prof.emotion = "assistant" if result.recommended_profile != "fast" else "focused"
        save_voice_profile(prof)
    except Exception:
        pass
    return result


def record_calibration_heard(*, expected: str, heard: str) -> bool:
    """Store expected vs heard pair from a live voice session (redacted)."""
    if not VOICE_CALIBRATION_ENABLED:
        return False
    safe_expected = _safe_text(expected)
    safe_heard = _safe_text(heard)
    if not safe_expected or not safe_heard:
        return False
    data = _load_payload()
    samples = list(data.get("samples") or [])
    updated = False
    for item in samples:
        if str(item.get("expected_phrase", "")).lower() == safe_expected.lower():
            item["heard_transcript"] = safe_heard
            item["normalized_transcript"] = _normalize(safe_heard)
            updated = True
            break
    if not updated:
        samples.append(
            {
                "expected_phrase": safe_expected,
                "heard_transcript": safe_heard,
                "normalized_transcript": _normalize(safe_heard),
            }
        )
    pairs: list[list[str]] = list(data.get("correction_pairs") or [])
    if safe_heard.lower() != safe_expected.lower():
        pair = [safe_heard.lower(), safe_expected.lower()]
        if pair not in pairs:
            pairs.append(pair)
    data["samples"] = samples[-VOICE_CALIBRATION_MAX_SAMPLES:]
    data["correction_pairs"] = pairs[-VOICE_CALIBRATION_MAX_SAMPLES:]
    data["recommended_profile"] = suggest_voice_profile(
        tuple(
            CalibrationSample(
                expected_phrase=str(s.get("expected_phrase", "")),
                heard_transcript=str(s.get("heard_transcript", "")),
                normalized_transcript=str(s.get("normalized_transcript", "")),
            )
            for s in data["samples"]
        )
    )
    data["pending"] = False
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_payload(data)
    return True


def apply_calibration_corrections(text: str) -> str:
    """Apply stored heard→expected correction pairs (deterministic)."""
    if not VOICE_CALIBRATION_ENABLED or not text.strip():
        return text
    data = _load_payload()
    lower = text.lower().strip()
    for heard, expected in data.get("correction_pairs") or []:
        if isinstance(heard, str) and isinstance(expected, str) and heard in lower:
            return expected
    return text


def reset_calibration_file() -> None:
    path = Path(VOICE_CALIBRATION_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def load_calibration_prompts() -> list[str]:
    data = _load_payload()
    prompts: list[str] = []
    for item in data.get("samples") or []:
        phrase = str(item.get("expected_phrase", "")).strip()
        if phrase:
            prompts.append(phrase)
    if prompts:
        return prompts[:VOICE_CALIBRATION_MAX_SAMPLES]
    return list(CALIBRATION_PROMPTS[:VOICE_CALIBRATION_MAX_SAMPLES])
