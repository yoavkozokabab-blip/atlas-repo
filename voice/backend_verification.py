"""Backend verification policy — conversational fallback vs tool-first gate (Phase 59.4)."""

from __future__ import annotations

from dataclasses import dataclass

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.backend_verification")

_last_probe: "BackendProbeResult | None" = None
_last_playback_test: "PlaybackTestResult | None" = None


@dataclass(frozen=True)
class BackendProbeResult:
    name: str
    initialized: bool
    verification_status: str
    playback_device: str
    playback_test: str
    init_error: str


@dataclass(frozen=True)
class PlaybackTestResult:
    success: bool
    backend: str
    device: str
    elapsed_ms: float
    error: str


def is_conversational_runtime_enabled() -> bool:
    try:
        from conversation.human_runtime import is_human_conversational_runtime_enabled

        return is_human_conversational_runtime_enabled()
    except Exception:
        return False


def is_local_tts_synthesis_available() -> bool:
    try:
        from voice.tts_status import get_tts_status

        tts = get_tts_status()
        if tts.pyttsx_available or tts.edge_available:
            return True
    except Exception:
        pass
    try:
        from voice.realtime_tts import is_realtime_tts_enabled

        return is_realtime_tts_enabled()
    except Exception:
        return False


def has_hard_playback_failure() -> bool:
    """Only hard failures should block conversational speech."""
    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        if audio.last_success is False and audio.last_error:
            err = (audio.last_error or "").lower()
            if any(token in err for token in ("timeout", "kill", "crash", "access denied")):
                return True
        if audio.playback_failure_count >= 3 and audio.last_success is False:
            return True
    except Exception:
        pass
    return False


def is_backend_initialized() -> bool:
    """True when a playback path is ready — not the same as user-verified metadata."""
    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        if audio.engine_active or audio.runloop_active:
            return True
        if audio.last_success is True:
            return True
        if audio.startup_self_test and str(audio.startup_self_test).startswith("ok"):
            return True
        if audio.active_backend not in {"", "none", "unknown", "unverified"}:
            return True
        if audio.playback_backend not in {"", "none", "unknown", "unverified"}:
            return True
    except Exception:
        pass

    ok, _, _ = probe_backend("pyttsx3", write_only=True)
    if ok:
        return True
    ok, _, _ = probe_backend("edge_tts", write_only=True)
    return ok


def has_verified_backend_metadata() -> bool:
    try:
        from voice.audio_verified import has_verified_audio_backend

        return has_verified_audio_backend()
    except Exception:
        return False


def conversational_playback_allowed(*, session_active: bool) -> tuple[bool, str]:
    """
    Allow conversational speech without verified-backend metadata when local playback is viable.
    Hard playback failures still block.
    """
    if not is_conversational_runtime_enabled():
        return False, ""
    if has_hard_playback_failure():
        return False, "playback_hard_failure"

    backend_ready = is_backend_initialized()
    synth_ok = is_local_tts_synthesis_available()

    if session_active and backend_ready:
        return True, "conversational_session_backend_ready"
    if session_active and synth_ok:
        return True, "conversational_session_local_synth"
    if backend_ready and synth_ok:
        return True, "conversational_runtime_local_fallback"
    return False, ""


def should_require_verified_backend_for_speech(*, session_active: bool = False) -> bool:
    allowed, _reason = conversational_playback_allowed(session_active=session_active)
    if allowed:
        return False
    try:
        from voice.tool_first_mode import is_tool_first_mode

        if is_tool_first_mode():
            return not has_verified_backend_metadata()
    except Exception:
        pass
    try:
        from voice.audio_verified import stable_requires_verified_backend

        if stable_requires_verified_backend():
            return not has_verified_backend_metadata()
    except Exception:
        pass
    return False


def probe_backend(name: str, *, write_only: bool = False) -> tuple[bool, str, str]:
    """Lightweight init probe; returns (ok, device, error)."""
    device = ""
    if name in {"pyttsx3", "pyttsx3_direct", "direct_pyttsx3", "pyttsx3_fallback"}:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            vid = engine.getProperty("voice")
            if voices and vid is not None:
                idx = int(vid) if isinstance(vid, (int, float)) else 0
                if 0 <= idx < len(voices):
                    device = str(getattr(voices[idx], "name", vid) or "default")[:80]
            try:
                engine.stop()
            except Exception:
                pass
            return True, device or "default", ""
        except Exception as exc:
            return False, device, str(exc)[:200]
    if name == "edge_tts":
        try:
            import edge_tts  # noqa: F401

            return True, "edge_stream", ""
        except Exception as exc:
            return False, "", str(exc)[:200]
    if name in {"subprocess_pyttsx3", "shell_subprocess_pyttsx3"}:
        try:
            from voice.windows_audio_routing import get_windows_default_playback_name

            return True, get_windows_default_playback_name() or "default", ""
        except Exception as exc:
            return False, "", str(exc)[:200]
    if write_only:
        return False, "", "unsupported"
    return False, "", "unsupported"


def _verification_status_for(name: str, *, initialized: bool) -> str:
    verified = has_verified_backend_metadata()
    try:
        from voice.audio_status import get_selected_verified_audio_backend

        selected = get_selected_verified_audio_backend()
        if selected and selected == name:
            return "verified"
    except Exception:
        pass
    if initialized and is_conversational_runtime_enabled():
        return "conversational_fallback"
    if initialized:
        return "initialized_unverified"
    return "not_initialized"


def format_backend_verification_diagnostics() -> str:
    global _last_probe
    try:
        from voice.audio_status import get_audio_status
        from voice.tts_backend import get_active_tts_backend

        audio = get_audio_status()
        active = get_active_tts_backend()
    except Exception:
        audio = None
        active = "unknown"

    candidates = [
        "pyttsx3",
        "direct_pyttsx3",
        "subprocess_pyttsx3",
        "edge_tts",
        "realtime",
    ]
    lines = [
        "Backend verification diagnostics:",
        f"  active backend (policy): {active}",
        f"  verified metadata: {audio.selected_verified_audio_backend if audio else 'none'}",
        f"  conversational runtime: {'yes' if is_conversational_runtime_enabled() else 'no'}",
        f"  backend initialized (policy): {'yes' if is_backend_initialized() else 'no'}",
        f"  local synth available: {'yes' if is_local_tts_synthesis_available() else 'no'}",
        f"  hard playback failure: {'yes' if has_hard_playback_failure() else 'no'}",
        "",
        "Backends:",
    ]
    for name in candidates:
        ok, device, err = probe_backend(name, write_only=True)
        status = _verification_status_for(name, initialized=ok)
        playback_test = "not_run"
        if _last_playback_test and _last_playback_test.backend == name:
            playback_test = "pass" if _last_playback_test.success else f"fail ({_last_playback_test.error})"
        lines.extend(
            [
                f"  - {name}:",
                f"      initialized: {'yes' if ok else 'no'}",
                f"      verification: {status}",
                f"      playback device: {device or 'n/a'}",
                f"      playback test: {playback_test}",
                f"      init error: {err or 'none'}",
            ]
        )
        _last_probe = BackendProbeResult(
            name=name,
            initialized=ok,
            verification_status=status,
            playback_device=device,
            playback_test=playback_test,
            init_error=err,
        )
    return "\n".join(lines)


def run_tts_playback_self_test(*, phrase: str = "JARVIS playback test.") -> PlaybackTestResult:
    """Synthesize and attempt playback; returns structured result."""
    import time

    global _last_playback_test
    t0 = time.perf_counter()
    backend = "unknown"
    device = ""
    error = ""
    success = False
    try:
        from voice.tts_output_policy import evaluate_tts_output

        decision = evaluate_tts_output(speak_enabled=True, voice_path="test_tts_playback")
        if not decision.allowed:
            error = decision.reason
            _last_playback_test = PlaybackTestResult(
                success=False,
                backend=backend,
                device=device,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                error=error,
            )
            return _last_playback_test
    except Exception as exc:
        error = str(exc)

    try:
        from voice.audio_status import get_audio_status, probe_output_device

        device = probe_output_device()
        backend = get_audio_status().active_backend or "default"
    except Exception:
        pass

    if not error:
        try:
            from voice.tts import TTSService, TTSError

            ok = TTSService(enabled=True).speak(phrase)
            success = bool(ok)
            if not ok:
                error = "speak_returned_false"
        except Exception as exc:
            from voice.tts import TTSError

            if isinstance(exc, TTSError):
                error = str(exc)
            else:
                error = str(exc)
            success = False

    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        backend = audio.active_backend or audio.playback_backend or backend
        if audio.output_device:
            device = audio.output_device
    except Exception:
        pass

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _last_playback_test = PlaybackTestResult(
        success=success,
        backend=backend,
        device=device,
        elapsed_ms=elapsed_ms,
        error=error,
    )
    logger.info(
        "TTS playback self-test success=%s backend=%s device=%s ms=%.1f err=%s",
        success,
        backend,
        device,
        elapsed_ms,
        error or "none",
    )
    return _last_playback_test


def format_tts_playback_self_test_report(result: PlaybackTestResult | None = None) -> str:
    result = result or _last_playback_test
    lines = ["TTS playback self-test:"]
    if result is None:
        lines.append("  status: not run")
        return "\n".join(lines)
    lines.extend(
        [
            f"  success: {'yes' if result.success else 'no'}",
            f"  backend path: {result.backend}",
            f"  playback device: {result.device or 'n/a'}",
            f"  elapsed ms: {result.elapsed_ms:.1f}",
            f"  error: {result.error or 'none'}",
            "",
            format_backend_verification_diagnostics(),
        ]
    )
    return "\n".join(lines)


def reset_backend_verification_for_tests() -> None:
    global _last_probe, _last_playback_test
    _last_probe = None
    _last_playback_test = None
