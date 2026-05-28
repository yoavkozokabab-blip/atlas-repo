"""Speech-to-text transcription (local, push-to-talk)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from config import (
    STT_BEAM_SIZE,
    STT_DEBUG_MIC,
    STT_ENABLE_NORMALIZATION,
    STT_ENGINE,
    STT_LANGUAGE,
    STT_LOW_CONFIDENCE_LOGPROB,
    STT_MODEL,
    STT_VAD_FILTER,
)
from voice.stt_acceleration import (
    force_cpu_fallback,
    force_faster_whisper_fallback,
    get_stt_runtime,
    print_stt_acceleration_startup,
)
from core.logger import setup_logger
from voice.stt_config import (
    ENGLISH_MODEL_HINT,
    HEBREW_MODEL_HINT,
    STT_LANGUAGES_ALLOWED,
    normalize_stt_model,
)

logger = setup_logger("jarvis.voice.stt")

_model_cache: object | None = None
_last_result: "TranscriptionResult | None" = None
_loaded_model_label: str | None = None
_loaded_compute_type: str | None = None


class TranscriptionError(Exception):
    """Raised when STT engine or model is unavailable."""


@dataclass
class TranscriptionResult:
    text: str
    language: str
    model: str
    device: str
    compute_type: str
    avg_logprob: float | None = None
    language_probability: float | None = None
    duration_seconds: float | None = None
    low_confidence: bool = False
    recommendation: str | None = None
    backends_used: list[str] | None = None
    fused_confidence: float | None = None
    repair_applied: bool = False
    retry_attempts: int = 1
    grammar_min_score: int | None = None


@dataclass
class SttStatus:
    engine: str
    model: str
    language: str
    device: str
    compute_type: str
    backend: str
    acceleration: str
    acceleration_reason: str
    fallback_reason: str | None
    normalization_enabled: bool
    model_loaded: bool
    loaded_label: str | None
    last_avg_logprob: float | None = None
    last_language_probability: float | None = None
    last_recommendation: str | None = None


def _whisper_device() -> str:
    return get_stt_runtime().whisper_device


def _resolve_compute_type(device: str) -> str:
    compute = get_stt_runtime().compute_type
    if compute:
        return compute
    return "float16" if device == "cuda" else "int8"


def _forced_language() -> str:
    """Whisper language code — forced (no auto-detect). Default English."""
    lang = (STT_LANGUAGE or "en").strip().lower()
    if lang not in STT_LANGUAGES_ALLOWED:
        return "en"
    return lang


def get_stt_status() -> SttStatus:
    device = _whisper_device()
    runtime = get_stt_runtime()
    return SttStatus(
        engine=STT_ENGINE,
        model=normalize_stt_model(STT_MODEL),
        language=_forced_language(),
        device=device,
        compute_type=_loaded_compute_type or _resolve_compute_type(device),
        backend=runtime.backend,
        acceleration=runtime.acceleration,
        acceleration_reason=runtime.reason,
        fallback_reason=runtime.fallback_reason,
        normalization_enabled=STT_ENABLE_NORMALIZATION,
        model_loaded=_model_cache is not None,
        loaded_label=_loaded_model_label,
        last_avg_logprob=_last_result.avg_logprob if _last_result else None,
        last_language_probability=(
            _last_result.language_probability if _last_result else None
        ),
        last_recommendation=_last_result.recommendation if _last_result else None,
    )


def format_stt_status(status: SttStatus | None = None) -> str:
    s = status or get_stt_status()
    runtime = get_stt_runtime()
    lines = [
        "STT status",
        f"  Engine: {s.engine}",
        f"  Backend: {s.backend}",
        f"  Model: {s.model}",
        f"  Language: {s.language} (forced for Whisper)",
        f"  Device: {s.device}",
        f"  Acceleration: {s.acceleration}",
        f"  ONNX provider: {runtime.onnx_provider}",
        f"  Reason: {s.acceleration_reason}",
        f"  Compute type: {s.compute_type}",
        f"  Normalization: {'on' if s.normalization_enabled else 'off'}",
        f"  Model loaded: {'yes' if s.model_loaded else 'no'}",
    ]
    if s.fallback_reason:
        lines.append(f"  Fallback: {s.fallback_reason}")
    if s.loaded_label:
        lines.append(f"  Loaded: {s.loaded_label}")
    if s.last_avg_logprob is not None:
        lines.append(f"  Last avg logprob: {s.last_avg_logprob:.3f}")
    if s.last_language_probability is not None:
        lines.append(f"  Last language probability: {s.last_language_probability:.3f}")
    if s.last_recommendation:
        lines.append(f"  Tip: {s.last_recommendation}")
    return "\n".join(lines)


def print_stt_startup_info() -> None:
    """Print STT configuration when voice subsystem may be used."""
    print_stt_acceleration_startup()
    s = get_stt_status()
    print(
        f"STT: engine={s.engine} model={s.model} language={s.language} "
        f"device={s.device} compute={s.compute_type} "
        f"backend={s.backend} acceleration={s.acceleration} "
        f"beam={STT_BEAM_SIZE} vad={STT_VAD_FILTER} "
        f"normalization={'on' if s.normalization_enabled else 'off'}",
        flush=True,
    )


def preload_stt_model() -> bool:
    """
    Load faster-whisper (or openai-whisper) once at startup.
    Returns True if model is ready.
    """
    if _model_cache is not None:
        device = _whisper_device()
        compute = _loaded_compute_type or _resolve_compute_type(device)
        model_name = normalize_stt_model(STT_MODEL)
        print(f"STT model preloaded: {model_name}/{compute}/{device}", flush=True)
        return True
    engine = STT_ENGINE.strip().lower().replace("-", "_")
    try:
        if engine in {"faster_whisper", "faster-whisper", "whisper"}:
            _load_faster_whisper()
        elif engine in {"openai_whisper", "openai-whisper"}:
            _load_openai_whisper()
        else:
            return False
    except TranscriptionError:
        return False
    device = _whisper_device()
    compute = _loaded_compute_type or _resolve_compute_type(device)
    model_name = normalize_stt_model(STT_MODEL)
    print(f"STT model preloaded: {model_name}/{compute}/{device}", flush=True)
    return _model_cache is not None


def get_last_transcription_feedback() -> str | None:
    if _last_result is None or not _last_result.recommendation:
        return None
    return _last_result.recommendation


def _evaluate_confidence(
    avg_logprob: float | None,
    language_probability: float | None,
    language: str,
) -> tuple[bool, str | None]:
    low = False
    if avg_logprob is not None and avg_logprob < STT_LOW_CONFIDENCE_LOGPROB:
        low = True
    if language_probability is not None and language_probability < 0.5:
        low = True
    if not low:
        return False, None
    if language == "he":
        hint = HEBREW_MODEL_HINT
    else:
        hint = ENGLISH_MODEL_HINT
    return True, hint


def _load_faster_whisper():
    global _model_cache, _loaded_model_label, _loaded_compute_type
    if _model_cache is not None:
        return _model_cache
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    model_name = normalize_stt_model(STT_MODEL)
    device = _whisper_device()
    compute_type = _resolve_compute_type(device)
    try:
        _model_cache = WhisperModel(model_name, device=device, compute_type=compute_type)
        _loaded_model_label = f"faster-whisper/{model_name} on {device} ({compute_type})"
        _loaded_compute_type = compute_type
        logger.info("Loaded STT model: %s", _loaded_model_label)
        print(f"STT model loaded: {_loaded_model_label}", flush=True)
    except Exception as exc:
        if device == "cuda":
            runtime = force_cpu_fallback(reason=str(exc))
            logger.warning("CUDA STT load failed, falling back to CPU: %s", exc)
            print(
                f"[WARNING] CUDA STT failed ({exc}); retrying on CPU ({runtime.compute_type}).",
                flush=True,
            )
            try:
                device = runtime.whisper_device
                compute_type = runtime.compute_type
                _model_cache = WhisperModel(
                    model_name, device=device, compute_type=compute_type
                )
                _loaded_model_label = (
                    f"faster-whisper/{model_name} on {device} ({compute_type})"
                )
                _loaded_compute_type = compute_type
                logger.info("Loaded STT model: %s", _loaded_model_label)
                print(f"STT model loaded: {_loaded_model_label}", flush=True)
            except Exception as cpu_exc:
                raise TranscriptionError(
                    f"Failed to load faster-whisper model '{model_name}': {cpu_exc}"
                ) from cpu_exc
        else:
            raise TranscriptionError(
                f"Failed to load faster-whisper model '{model_name}': {exc}"
            ) from exc
    return _model_cache


def _load_openai_whisper():
    global _model_cache, _loaded_model_label, _loaded_compute_type
    if _model_cache is not None:
        return _model_cache
    try:
        import whisper
    except ImportError as exc:
        raise TranscriptionError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc
    model_name = normalize_stt_model(STT_MODEL)
    device = _whisper_device()
    try:
        _model_cache = whisper.load_model(model_name, device=device)
        _loaded_model_label = f"openai-whisper/{model_name} on {device}"
        _loaded_compute_type = device
        logger.info("Loaded STT model: %s", _loaded_model_label)
        print(f"STT model loaded: {_loaded_model_label}", flush=True)
    except Exception as exc:
        raise TranscriptionError(
            f"Failed to load whisper model '{model_name}': {exc}"
        ) from exc
    return _model_cache


def _prepare_audio(path: Path) -> tuple[object, int]:
    """Return (audio array float32, sample_rate)."""
    from faster_whisper.audio import decode_audio

    import numpy as np

    audio = decode_audio(str(path))
    audio = np.squeeze(audio).astype(np.float32)
    if STT_ENABLE_NORMALIZATION:
        from voice.audio_preprocess import normalize_audio_float

        audio = normalize_audio_float(audio)
    return audio, 16000


def transcribe_audio(path: Path | str) -> str:
    """Transcribe WAV to text; stores detailed result for status / feedback."""
    return transcribe_audio_detailed(path).text


def transcribe_wake_audio_fast(path: Path | str) -> TranscriptionResult:
    """
    Wake fallback after streaming failure: legacy faster_whisper only (no multipass/stack).
    Bounded timeout to avoid 45s hangs.
    """
    import config as cfg
    from services.runtime_monitor import OperationTimeoutError, run_with_timeout

    audio_path = Path(path)
    if not audio_path.is_file():
        raise TranscriptionError(f"Audio file not found: {audio_path}")

    try:
        return run_with_timeout(
            "stt.wake.fast",
            cfg.STT_WAKE_FALLBACK_TIMEOUT_SECONDS,
            _transcribe_faster_whisper,
            audio_path,
            detail=str(audio_path),
        )
    except OperationTimeoutError as exc:
        raise TranscriptionError(
            f"Wake STT fast fallback timeout after {cfg.STT_WAKE_FALLBACK_TIMEOUT_SECONDS:.1f}s"
        ) from exc


def transcribe_audio_detailed(path: Path | str) -> TranscriptionResult:
    import config as cfg
    from services.runtime_monitor import (
        OperationTimeoutError,
        get_runtime_monitor,
        run_with_timeout,
    )

    t0 = time.perf_counter()
    try:
        result = run_with_timeout(
            "stt.transcribe",
            cfg.STT_TIMEOUT_SECONDS,
            _transcribe_audio_detailed_inner,
            path,
            detail=str(path),
        )
    except OperationTimeoutError as exc:
        reset_model_cache()
        get_runtime_monitor().record_recovery(
            "stt",
            "reset_model_cache",
            reason=str(exc),
            ok=True,
        )
        try:
            from services.observability import get_observability

            get_observability().record_failure(
                component="stt",
                error=exc,
                context={"path": str(path), "timeout_seconds": cfg.STT_TIMEOUT_SECONDS},
            )
        except Exception:
            pass
        raise TranscriptionError(
            f"STT timeout after {cfg.STT_TIMEOUT_SECONDS:.1f}s; model cache reset."
        ) from exc
    except Exception as exc:
        try:
            from services.observability import get_observability

            get_observability().record_failure(
                component="stt",
                error=exc,
                context={"path": str(path)},
            )
        except Exception:
            pass
        raise
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    try:
        from services.observability import get_observability

        obs = get_observability()
        obs.record_latency(
            "stt.transcribe",
            elapsed_ms,
            model=result.model,
            device=result.device,
            low_confidence=result.low_confidence,
        )
        obs.profile_stage(
            "voice",
            "stt",
            elapsed_ms,
            model=result.model,
            device=result.device,
        )
    except Exception:
        pass
    return result


def _transcribe_audio_detailed_inner(path: Path | str) -> TranscriptionResult:
    global _last_result

    audio_path = Path(path)
    if not audio_path.is_file():
        raise TranscriptionError(f"Audio file not found: {audio_path}")

    try:
        from voice.stt_stack.multipass import is_multipass_enabled, transcribe_multipass

        if is_multipass_enabled():
            result = transcribe_multipass(audio_path)
            _last_result = result
            if result.recommendation:
                logger.info("STT low confidence: %s", result.recommendation)
                print(f"[STT] {result.recommendation}", flush=True)
            return result
    except Exception as exc:
        logger.warning("STT multipass failed, falling back: %s", exc)

    try:
        from voice.stt_stack.stt_controller import is_stack_enabled, transcribe_with_stack

        if is_stack_enabled():
            result = transcribe_with_stack(audio_path)
            _last_result = result
            if result.recommendation:
                logger.info("STT low confidence: %s", result.recommendation)
                print(f"[STT] {result.recommendation}", flush=True)
            return result
    except Exception as exc:
        logger.warning("STT stack failed, using legacy path: %s", exc)

    from config import STT_PREFER_DIRECTML

    engine = STT_ENGINE.strip().lower().replace("-", "_")
    runtime = get_stt_runtime()
    if (
        STT_PREFER_DIRECTML
        and runtime.backend == "onnx_directml"
        and engine in {
        "faster_whisper",
        "faster-whisper",
        "whisper",
        }
    ):
        try:
            result = _transcribe_onnx_directml(audio_path)
        except Exception as exc:
            logger.warning("DirectML STT failed, falling back to CPU faster-whisper: %s", exc)
            print(
                f"[WARNING] DirectML STT failed ({exc}); using CPU faster-whisper.",
                flush=True,
            )
            force_faster_whisper_fallback(reason=str(exc))
            from voice.stt_directml import reset_directml_model_cache

            reset_directml_model_cache()
            reset_model_cache()
            result = _transcribe_faster_whisper(audio_path)
    elif engine in {"faster_whisper", "faster-whisper", "whisper"}:
        result = _transcribe_faster_whisper(audio_path)
    elif engine in {"openai_whisper", "openai-whisper"}:
        result = _transcribe_openai_whisper(audio_path)
    else:
        raise TranscriptionError(
            f"Unknown STT_ENGINE '{STT_ENGINE}'. Use faster_whisper or openai_whisper."
        )
    _last_result = result
    if result.recommendation:
        logger.info("STT low confidence: %s", result.recommendation)
        print(f"[STT] {result.recommendation}", flush=True)
    return result


def _transcribe_onnx_directml(audio_path: Path) -> TranscriptionResult:
    from config import STT_PREFER_DIRECTML
    from voice.stt_directml import transcribe_onnx_directml

    lang = _forced_language()
    model_name = normalize_stt_model(STT_MODEL)
    runtime = get_stt_runtime()
    text, provider, label = transcribe_onnx_directml(
        audio_path,
        stt_model=model_name,
        language=lang,
        prefer_directml=STT_PREFER_DIRECTML,
    )
    global _loaded_model_label, _loaded_compute_type
    _loaded_model_label = label
    _loaded_compute_type = runtime.compute_type
    low, rec = _evaluate_confidence(None, None, lang)
    return TranscriptionResult(
        text=text,
        language=lang,
        model=model_name,
        device=runtime.whisper_device,
        compute_type=runtime.compute_type,
        avg_logprob=None,
        language_probability=None,
        duration_seconds=None,
        low_confidence=low,
        recommendation=rec,
    )


def _transcribe_faster_whisper(
    audio_path: Path,
    *,
    beam_size: int | None = None,
    language: str | None = None,
) -> TranscriptionResult:
    model = _load_faster_whisper()
    lang = language or _forced_language()
    device = _whisper_device()
    compute = _loaded_compute_type or _resolve_compute_type(device)
    model_name = normalize_stt_model(STT_MODEL)
    beam = max(1, beam_size if beam_size is not None else STT_BEAM_SIZE)

    try:
        audio, _sr = _prepare_audio(audio_path)
        # language= forces Whisper (no auto-detect); en mode is English-only
        segments, info = model.transcribe(
            audio,
            language=lang,
            task="transcribe",
            beam_size=beam,
            vad_filter=STT_VAD_FILTER,
            condition_on_previous_text=False,
        )
        parts: list[str] = []
        logprobs: list[float] = []
        for seg in segments:
            if seg.text.strip():
                parts.append(seg.text.strip())
            if seg.avg_logprob is not None:
                logprobs.append(float(seg.avg_logprob))
        text = " ".join(parts).strip()
        avg_lp = sum(logprobs) / len(logprobs) if logprobs else None
        lang_prob = getattr(info, "language_probability", None)
        duration = getattr(info, "duration", None)
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    low, rec = _evaluate_confidence(avg_lp, lang_prob, lang)
    return TranscriptionResult(
        text=text,
        language=lang,
        model=model_name,
        device=device,
        compute_type=compute,
        avg_logprob=avg_lp,
        language_probability=float(lang_prob) if lang_prob is not None else None,
        duration_seconds=float(duration) if duration is not None else None,
        low_confidence=low,
        recommendation=rec,
    )


def _transcribe_openai_whisper(audio_path: Path) -> TranscriptionResult:
    model = _load_openai_whisper()
    lang = _forced_language()
    device = _whisper_device()
    model_name = normalize_stt_model(STT_MODEL)
    try:
        result = model.transcribe(str(audio_path), language=lang, task="transcribe")
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc
    text = (result.get("text") or "").strip()
    segments = result.get("segments") or []
    logprobs = [
        float(s["avg_logprob"])
        for s in segments
        if s.get("avg_logprob") is not None
    ]
    avg_lp = sum(logprobs) / len(logprobs) if logprobs else None
    low, rec = _evaluate_confidence(avg_lp, None, lang)
    return TranscriptionResult(
        text=text,
        language=lang,
        model=model_name,
        device=device,
        compute_type=device,
        avg_logprob=avg_lp,
        low_confidence=low,
        recommendation=rec,
    )


def transcribe_faster_whisper_hypothesis(
    audio_path: Path,
    *,
    language: str,
    on_partial=None,
    beam_size: int | None = None,
    max_ms: float | None = None,
    stt_pass: str = "full",
) -> "SttHypothesis":
    """Public helper for faster_whisper STT engine (Phase 42)."""
    from voice.stt_engines.base import SttHypothesis, logprob_to_confidence

    import config as cfg

    pass_mode = (stt_pass or "full").strip().lower()
    effective_beam = beam_size
    timeout_name = "stt.decode"
    timeout_s: float | None = None

    if pass_mode == "partial":
        effective_beam = 1
        timeout_name = "stt.stream.partial"
        if max_ms is not None:
            timeout_s = max(0.5, float(max_ms) / 1000.0)
        else:
            timeout_s = max(0.5, cfg.stt_stream_partial_timeout_ms() / 1000.0)
    elif pass_mode == "accurate":
        timeout_name = "stt.accurate_retry"
        if max_ms is not None:
            timeout_s = max(1.0, float(max_ms) / 1000.0)
        else:
            timeout_s = max(1.0, float(cfg.STT_ACCURATE_RETRY_MAX_MS) / 1000.0)
    elif max_ms is not None and max_ms > 0:
        timeout_s = max(0.5, float(max_ms) / 1000.0)

    def _run() -> TranscriptionResult:
        return _transcribe_faster_whisper(
            Path(audio_path),
            beam_size=effective_beam,
            language=language,
        )

    if timeout_s is not None and timeout_s > 0:
        from services.runtime_monitor import run_with_timeout

        result = run_with_timeout(
            timeout_name,
            timeout_s,
            _run,
            detail=str(audio_path),
        )
    else:
        result = _run()
    if on_partial and result.text:
        on_partial(result.text)
    return SttHypothesis(
        text=result.text,
        engine="faster_whisper",
        confidence=logprob_to_confidence(result.avg_logprob),
        language=result.language,
        avg_logprob=result.avg_logprob,
        language_probability=result.language_probability,
    )


def reset_model_cache() -> None:
    """Clear cached model (for tests)."""
    global _model_cache, _last_result, _loaded_model_label, _loaded_compute_type
    _model_cache = None
    _last_result = None
    _loaded_model_label = None
    _loaded_compute_type = None
    try:
        from voice.stt_directml import reset_directml_model_cache

        reset_directml_model_cache()
    except Exception:
        pass
