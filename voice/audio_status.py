"""TTS/audio playback diagnostics (read-only + test helpers)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config import TTS_ASYNC, TTS_ENABLED, TTS_ENGINE, TTS_FORCE_ENGINE
from voice.tts_config import normalize_tts_engine
from voice.tts_status import get_tts_status


@dataclass
class AudioStatus:
    enabled: bool
    engine: str
    playback_backend: str
    fallback_active: bool
    async_mode: bool
    safe_mode: bool
    last_success: bool | None
    last_provider: str | None
    last_error: str | None
    last_exception: str
    playback_failure_count: int
    last_spoken_preview: str
    last_spoken_at: str | None
    async_failure_count: int
    output_device: str
    startup_self_test: str | None
    direct_speech_last_success_at: str | None
    normal_speech_last_success_at: str | None
    normal_speech_last_error: str | None
    normal_speech_last_path: str | None
    stable_normal_equals_direct: bool | None
    direct_pyttsx3_user_heard: bool | None
    winsound_user_heard: bool | None
    wav_winsound_user_heard: bool | None
    sounddevice_user_heard: bool | None
    selected_verified_audio_backend: str | None
    force_direct_normal_mode: bool
    direct_engine_last_completed_at: str | None
    active_backend: str
    windows_default_output: str
    playback_target: str
    sonar_detected: bool
    active_playback_route: str
    audible_route_verified: bool
    active_tts_pid: int | None
    tts_started_at: str | None
    tts_elapsed_ms: float | None
    last_timeout_kill_reason: str | None
    last_subprocess_exit_code: int | None
    last_subprocess_error: str | None
    playback_audible_confirmed: bool
    completion_hang_detected: bool
    com_recovery_mode_active: bool
    speech_success_heuristic_active: bool
    runloop_active: bool
    engine_active: bool
    speech_lock_held: bool
    delayed_completion_recovered: bool
    completion_grace_active: bool
    worker_grace_elapsed_ms: float | None
    completion_pipeline_version: str
    grace_recovery_enabled: bool
    active_completion_handler: str
    legacy_completion_path_detected: bool
    debug_force_enabled: bool


_last_spoken_preview: str = ""
_last_spoken_at: str | None = None
_fallback_active: bool = False
_startup_self_test: str | None = None
_output_device: str = "default"
_direct_last_success_at: str | None = None
_normal_last_success_at: str | None = None
_normal_last_error: str | None = None
_normal_last_path: str | None = None
_direct_pyttsx3_user_heard: bool | None = None
_winsound_user_heard: bool | None = None
_wav_winsound_user_heard: bool | None = None
_sounddevice_user_heard: bool | None = None
_selected_verified_audio_backend: str | None = None
_force_direct_normal_mode: bool = False
_direct_engine_last_completed_at: str | None = None
_last_subprocess_exit_code: int | None = None
_last_subprocess_error: str | None = None
_last_timeout_kill_reason: str | None = None
_completion_hang_detected: bool = False
_com_recovery_mode_active: bool = False
_speech_success_heuristic_active: bool = False
_delayed_completion_recovered: bool = False
_completion_grace_active: bool = False
_worker_grace_elapsed_ms: float | None = None
_completion_pipeline_version: str = "unknown"
_grace_recovery_enabled: bool = False
_active_completion_handler: str = "unknown"
_legacy_completion_path_detected: bool = True
_debug_force_enabled: bool = False
_debug_force_applied: bool = False


def record_tts_timeout_kill(reason: str) -> None:
    global _last_timeout_kill_reason, _normal_last_error
    _last_timeout_kill_reason = (reason or "timeout")[:300]
    _normal_last_error = _last_timeout_kill_reason


def record_subprocess_tts_result(result: object) -> None:
    global _last_subprocess_exit_code, _last_subprocess_error
    exit_code = int(getattr(result, "exit_code", -1))
    stderr = (getattr(result, "stderr", "") or "").strip()
    timed_out = bool(getattr(result, "timed_out", False))
    _last_subprocess_exit_code = exit_code
    if timed_out:
        _last_subprocess_error = (stderr or "subprocess timeout")[:300]
    elif exit_code != 0:
        _last_subprocess_error = (stderr or f"exit {exit_code}")[:300]
    else:
        _last_subprocess_error = None


def record_tts_failure(*, error: str, provider: str = "") -> None:
    try:
        from voice.tts_status import record_tts_async_failure

        record_tts_async_failure(error, provider=provider or None)
    except Exception:
        pass


def record_tts_success(*, provider: str, text_preview: str) -> None:
    """User-confirmed or explicitly verified audible success (not runAndWait alone)."""
    global _last_spoken_preview, _last_spoken_at, _fallback_active
    _last_spoken_preview = (text_preview or "")[:80]
    _last_spoken_at = datetime.now(timezone.utc).isoformat()
    if "fallback" in provider or provider == "pyttsx3":
        _fallback_active = True
    else:
        _fallback_active = False


def record_direct_engine_completed(*, text_preview: str = "") -> None:
    global _direct_engine_last_completed_at
    _direct_engine_last_completed_at = datetime.now(timezone.utc).isoformat()
    if text_preview:
        _last_spoken_preview = text_preview[:80]


def record_direct_speech_success(*, text_preview: str = "") -> None:
    global _direct_last_success_at
    _direct_last_success_at = datetime.now(timezone.utc).isoformat()
    if text_preview:
        record_tts_success(provider="pyttsx3_direct", text_preview=text_preview)


def record_normal_speech_success(*, text_preview: str = "", path: str = "") -> None:
    global _normal_last_success_at, _normal_last_error, _normal_last_path
    _normal_last_success_at = datetime.now(timezone.utc).isoformat()
    _normal_last_error = None
    if path:
        _normal_last_path = path[:80]
    if text_preview and user_confirmed_direct_audio():
        record_tts_success(provider=path or "normal", text_preview=text_preview)


def record_normal_speech_failure(error: str) -> None:
    global _normal_last_error
    _normal_last_error = (error or "")[:300]


def record_normal_speech_path(path: str) -> None:
    global _normal_last_path
    _normal_last_path = (path or "")[:80]


def record_user_heard_result(method: str, heard: bool | None) -> None:
    global _direct_pyttsx3_user_heard, _winsound_user_heard
    global _wav_winsound_user_heard, _sounddevice_user_heard
    if heard is None:
        return
    if method == "direct_pyttsx3":
        _direct_pyttsx3_user_heard = heard
        if heard:
            record_direct_speech_success()
    elif method == "winsound":
        _winsound_user_heard = heard
    elif method == "wav_winsound":
        _wav_winsound_user_heard = heard
    elif method == "sounddevice":
        _sounddevice_user_heard = heard


def set_selected_verified_audio_backend(backend: str | None) -> None:
    global _selected_verified_audio_backend
    _selected_verified_audio_backend = (backend or None)[:80] if backend else None


def apply_verified_direct_pyttsx3_backend(*, user_heard: bool = True) -> None:
    """Mark direct pyttsx3 as the verified normal speech backend (stable mode)."""
    from voice.tts_backend import DIRECT_PYTTSX3_BACKEND

    global _direct_pyttsx3_user_heard, _normal_last_path, _normal_last_error
    set_selected_verified_audio_backend(DIRECT_PYTTSX3_BACKEND)
    _direct_pyttsx3_user_heard = bool(user_heard)
    _normal_last_path = "pyttsx3_direct"
    _normal_last_error = None
    try:
        import config as cfg

        cfg.TTS_BACKEND = DIRECT_PYTTSX3_BACKEND
    except Exception:
        pass


def is_debug_force_audio_enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "FORCE_AUDIO_SUCCESS_FOR_DEBUG", False))
    except Exception:
        return False


def apply_force_audio_success_for_debug_at_startup() -> bool:
    """
    Debug-only: at startup, auto-verify direct_pyttsx3 and bypass stable speech block.
    """
    global _debug_force_enabled, _debug_force_applied
    _debug_force_enabled = is_debug_force_audio_enabled()
    if not _debug_force_enabled:
        return False
    if _debug_force_applied:
        return True
    print("[AUDIO_DEBUG] force audio success enabled", flush=True)
    apply_verified_direct_pyttsx3_backend(user_heard=True)
    mark_speech_success_heuristic_active()
    _debug_force_applied = True
    return True


def ensure_force_audio_debug_applied() -> bool:
    """Idempotent apply for runtime gates that run after startup."""
    if not is_debug_force_audio_enabled():
        return False
    return apply_force_audio_success_for_debug_at_startup()


def maybe_auto_verify_direct_speech_debug() -> None:
    """Debug-only: successful direct speech auto-verifies backend (no manual yes/no)."""
    try:
        import config as cfg

        if not getattr(cfg, "FORCE_AUDIO_SUCCESS_FOR_DEBUG", False):
            return
    except Exception:
        return
    apply_verified_direct_pyttsx3_backend(user_heard=True)
    mark_speech_success_heuristic_active()


def get_selected_verified_audio_backend() -> str | None:
    return _selected_verified_audio_backend


def is_force_direct_normal_mode() -> bool:
    return _force_direct_normal_mode


def set_force_direct_normal_mode(enabled: bool = True) -> None:
    global _force_direct_normal_mode, _normal_last_path
    _force_direct_normal_mode = bool(enabled)
    try:
        import config as cfg

        cfg.TTS_BACKEND = "pyttsx3_direct" if enabled else "subprocess_pyttsx3"
    except Exception:
        pass
    if enabled:
        _normal_last_path = "pyttsx3_direct"


def playback_audible_confirmed() -> bool:
    return user_confirmed_direct_audio()


def _lifecycle_flag(name: str) -> bool:
    try:
        from voice.pyttsx3_lifecycle import get_lifecycle_snapshot

        return bool(get_lifecycle_snapshot().get(name))
    except Exception:
        return False


def record_completion_hang() -> None:
    global _completion_hang_detected, _com_recovery_mode_active
    _completion_hang_detected = True
    _com_recovery_mode_active = True


def mark_speech_success_heuristic_active() -> None:
    global _speech_success_heuristic_active
    _speech_success_heuristic_active = True


def set_completion_grace_active(*, active: bool, elapsed_ms: float = 0.0) -> None:
    global _completion_grace_active, _worker_grace_elapsed_ms
    _completion_grace_active = bool(active)
    if active:
        _worker_grace_elapsed_ms = max(0.0, float(elapsed_ms))
    elif not _delayed_completion_recovered:
        _worker_grace_elapsed_ms = max(0.0, float(elapsed_ms))


def clear_completion_grace() -> None:
    global _completion_grace_active
    _completion_grace_active = False


def record_delayed_completion_recovered() -> None:
    global _delayed_completion_recovered, _completion_hang_detected, _com_recovery_mode_active
    _delayed_completion_recovered = True
    _completion_hang_detected = True
    _com_recovery_mode_active = True


def register_completion_pipeline_at_startup(
    *,
    version: str,
    handler: str,
    grace_recovery_enabled: bool,
    heuristic_enabled: bool,
    legacy_detected: bool,
    source_file: str = "",
) -> None:
    global _completion_pipeline_version, _grace_recovery_enabled, _active_completion_handler
    global _legacy_completion_path_detected
    global _debug_force_enabled, _debug_force_applied
    _completion_pipeline_version = (version or "unknown")[:32]
    _grace_recovery_enabled = bool(grace_recovery_enabled)
    _active_completion_handler = (handler or "unknown")[:160]
    _legacy_completion_path_detected = bool(legacy_detected)
    if legacy_detected:
        print(
            "[WARNING] legacy completion path active "
            f"(handler={_active_completion_handler} source={source_file or 'n/a'})",
            flush=True,
        )
    elif not grace_recovery_enabled:
        print(
            "[WARNING] completion grace recovery disabled via config",
            flush=True,
        )
    del heuristic_enabled


def register_completion_pipeline_invocation(
    *,
    version: str,
    handler: str,
    grace_recovery_enabled: bool,
    heuristic_enabled: bool,
    legacy_detected: bool,
) -> None:
    global _completion_pipeline_version, _grace_recovery_enabled, _active_completion_handler
    global _legacy_completion_path_detected
    global _debug_force_enabled, _debug_force_applied
    _completion_pipeline_version = (version or _completion_pipeline_version)[:32]
    _grace_recovery_enabled = bool(grace_recovery_enabled)
    _active_completion_handler = (handler or _active_completion_handler)[:160]
    _legacy_completion_path_detected = bool(legacy_detected)
    del heuristic_enabled


def warn_if_legacy_completion_path_active() -> None:
    if _legacy_completion_path_detected:
        print(
            "[WARNING] legacy completion path active — completion_grace_start will not run; "
            "restart JARVIS to load voice/pyttsx3_completion.py v2",
            flush=True,
        )


def recent_completion_hang_success(*, within_seconds: float = 8.0) -> bool:
    try:
        from voice.pyttsx3_completion import recent_completion_hang_success as _recent

        return _recent(within_seconds=within_seconds)
    except Exception:
        return False


def user_confirmed_direct_audio() -> bool:
    if is_debug_force_audio_enabled() and _debug_force_applied:
        return True
    if _direct_pyttsx3_user_heard is True:
        return True
    if _selected_verified_audio_backend == "direct_pyttsx3":
        return True
    return False


def stable_normal_equals_direct() -> bool | None:
    try:
        from voice.tts_playback_trace import is_tts_safe_mode

        if not is_tts_safe_mode():
            return None
    except Exception:
        return None
    if _selected_verified_audio_backend == "direct_pyttsx3":
        return True
    if _normal_last_path is None:
        return None
    return _normal_last_path in {
        "pyttsx3_direct",
        "direct_pyttsx3",
        "subprocess_pyttsx3",
        "shell_subprocess_pyttsx3",
    }


def warn_stable_path_mismatch_if_needed() -> None:
    if stable_normal_equals_direct() is not False:
        return
    msg = "Stable TTS is not using direct pyttsx3 path."
    print(f"[TTS ERROR] {msg}", flush=True)
    try:
        from ui.overlay_app import notify_overlay_error

        notify_overlay_error(msg)
    except Exception:
        pass


def set_fallback_active(active: bool) -> None:
    global _fallback_active
    _fallback_active = active


def set_startup_self_test_result(msg: str) -> None:
    global _startup_self_test
    _startup_self_test = (msg or "")[:200]


def probe_output_device() -> str:
    global _output_device
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        vid = engine.getProperty("voice")
        name = "default"
        if voices and vid is not None:
            idx = int(vid) if isinstance(vid, (int, float)) else 0
            if 0 <= idx < len(voices):
                name = getattr(voices[idx], "name", str(vid)) or "default"
        _output_device = str(name)[:80]
        try:
            engine.stop()
        except Exception:
            pass
    except Exception as exc:
        _output_device = f"unavailable ({exc})"[:80]
    return _output_device


def get_audio_status() -> AudioStatus:
    tts = get_tts_status()
    engine = normalize_tts_engine(TTS_FORCE_ENGINE or TTS_ENGINE)
    try:
        from voice.tts_backend import get_active_tts_backend

        active_backend = get_active_tts_backend()
    except Exception:
        active_backend = "unknown"
    if _normal_last_path:
        playback = _normal_last_path
    elif _selected_verified_audio_backend:
        playback = _selected_verified_audio_backend
    elif active_backend not in ("", "default", "unverified", "unknown"):
        playback = active_backend
    else:
        playback = tts.last_provider or engine
    backend = playback
    if _fallback_active or (tts.last_provider or "").endswith("fallback"):
        backend = f"{backend} (fallback active)"
    try:
        from voice.tts_playback_trace import get_playback_snapshot, is_tts_safe_mode

        snap = get_playback_snapshot()
        last_exc = snap.last_exception
        fail_count = snap.failure_count
        safe = is_tts_safe_mode()
    except Exception:
        last_exc = ""
        fail_count = 0
        safe = False
    try:
        from voice.windows_audio_routing import (
            detect_steelseries_sonar,
            get_windows_default_playback_name,
            resolve_subprocess_playback_route,
        )
        from voice.audio_devices import (
            get_persisted_playback_target,
            is_audible_route_verified,
        )

        route = resolve_subprocess_playback_route()
        windows_default = get_windows_default_playback_name()
        playback_target = get_persisted_playback_target()
        sonar_detected = detect_steelseries_sonar()
        active_route = route.device_label
        audible_verified = is_audible_route_verified()
        from voice.tts_watchdog import (
            get_active_tts_pid,
            get_last_kill_reason,
            get_speak_elapsed_ms,
            get_speak_started_at,
        )

        active_pid = get_active_tts_pid()
        started_wall = get_speak_started_at()
        tts_started_iso = None
        if started_wall is not None:
            tts_started_iso = datetime.fromtimestamp(
                started_wall, tz=timezone.utc
            ).isoformat()
        tts_elapsed = get_speak_elapsed_ms()
        timeout_reason = get_last_kill_reason() or _last_timeout_kill_reason
    except Exception:
        windows_default = "n/a"
        playback_target = "default"
        sonar_detected = False
        active_route = "n/a"
        audible_verified = False
        active_pid = None
        tts_started_iso = None
        tts_elapsed = None
        timeout_reason = _last_timeout_kill_reason

    return AudioStatus(
        enabled=TTS_ENABLED,
        engine=engine,
        playback_backend=backend,
        active_backend=active_backend,
        windows_default_output=windows_default,
        playback_target=playback_target,
        sonar_detected=sonar_detected,
        active_playback_route=active_route,
        audible_route_verified=audible_verified,
        active_tts_pid=active_pid,
        tts_started_at=tts_started_iso,
        tts_elapsed_ms=tts_elapsed,
        last_timeout_kill_reason=timeout_reason,
        last_subprocess_exit_code=_last_subprocess_exit_code,
        last_subprocess_error=_last_subprocess_error,
        fallback_active=_fallback_active or "fallback" in (tts.last_provider or ""),
        async_mode=TTS_ASYNC,
        safe_mode=safe,
        last_success=(
            True
            if _selected_verified_audio_backend == "direct_pyttsx3"
            and (_direct_pyttsx3_user_heard is True or _direct_engine_last_completed_at)
            else (
                True
                if _selected_verified_audio_backend
                and _selected_verified_audio_backend != "direct_pyttsx3"
                and _last_subprocess_exit_code == 0
                else (tts.last_success if user_confirmed_direct_audio() else None)
            )
        ),
        last_provider=tts.last_provider,
        last_error=tts.last_error or last_exc,
        last_exception=last_exc,
        playback_failure_count=fail_count,
        last_spoken_preview=_last_spoken_preview,
        last_spoken_at=_last_spoken_at if user_confirmed_direct_audio() else None,
        async_failure_count=tts.async_failure_count,
        output_device=_output_device or probe_output_device(),
        startup_self_test=_startup_self_test,
        direct_speech_last_success_at=_direct_last_success_at,
        normal_speech_last_success_at=_normal_last_success_at,
        normal_speech_last_error=_normal_last_error,
        normal_speech_last_path=_normal_last_path,
        stable_normal_equals_direct=stable_normal_equals_direct(),
        direct_pyttsx3_user_heard=_direct_pyttsx3_user_heard,
        winsound_user_heard=_winsound_user_heard,
        wav_winsound_user_heard=_wav_winsound_user_heard,
        sounddevice_user_heard=_sounddevice_user_heard,
        selected_verified_audio_backend=_selected_verified_audio_backend,
        force_direct_normal_mode=_force_direct_normal_mode,
        direct_engine_last_completed_at=_direct_engine_last_completed_at,
        playback_audible_confirmed=playback_audible_confirmed(),
        completion_hang_detected=_completion_hang_detected,
        com_recovery_mode_active=_com_recovery_mode_active,
        speech_success_heuristic_active=_speech_success_heuristic_active,
        runloop_active=_lifecycle_flag("runloop_active"),
        engine_active=_lifecycle_flag("engine_active"),
        speech_lock_held=_lifecycle_flag("speech_lock_held"),
        delayed_completion_recovered=_delayed_completion_recovered,
        completion_grace_active=_completion_grace_active,
        worker_grace_elapsed_ms=_worker_grace_elapsed_ms,
        completion_pipeline_version=_completion_pipeline_version,
        grace_recovery_enabled=_grace_recovery_enabled,
        active_completion_handler=_active_completion_handler,
        legacy_completion_path_detected=_legacy_completion_path_detected,
        debug_force_enabled=_debug_force_enabled,
    )


_AUDIO_STATUS_REQUIRED_MARKERS: tuple[str, ...] = (
    "Completion pipeline version:",
    "Grace recovery enabled:",
    "Active completion handler:",
    "Legacy path detected:",
    "Debug force enabled:",
)


def validate_audio_status_model() -> None:
    body = format_audio_status()
    missing = [marker for marker in _AUDIO_STATUS_REQUIRED_MARKERS if marker not in body]
    if missing:
        print(
            f"[AUDIO] status model mismatch detected missing={','.join(missing)}",
            flush=True,
        )


def format_audio_status() -> str:
    ensure_force_audio_debug_applied()
    s = get_audio_status()
    lines = [
        "Audio status",
        f"  TTS enabled: {'yes' if s.enabled else 'no'}",
        f"  Current engine (config): {s.engine}",
        "  TTS chain: edge_tts -> pyttsx3 (direct verified backend bypasses subprocess)",
        f"  Verified backend: {s.selected_verified_audio_backend or 'none (speech blocked in stable)'}",
        f"  Active backend: {s.active_backend}",
        f"  Playback backend (last used): {s.playback_backend}",
        f"  Last normal speech backend: {s.normal_speech_last_path or 'n/a'}",
        f"  Windows default output: {s.windows_default_output}",
        f"  Playback target (persisted): {s.playback_target}",
        f"  Active playback route: {s.active_playback_route}",
        f"  Sonar detected: {'yes' if s.sonar_detected else 'no'}",
        f"  Audible route verified: {'yes' if s.audible_route_verified else 'no'}",
        f"  Active TTS pid: {s.active_tts_pid if s.active_tts_pid is not None else 'n/a'}",
        f"  TTS started at: {s.tts_started_at or 'n/a'}",
        f"  TTS elapsed ms: {f'{s.tts_elapsed_ms:.0f}' if s.tts_elapsed_ms is not None else 'n/a'}",
        f"  Last timeout/killed: {s.last_timeout_kill_reason or 'n/a'}",
        f"  Fallback active: {'yes' if s.fallback_active else 'no'}",
        f"  Async mode: {'yes' if s.async_mode else 'no'}",
        f"  TTS safe mode: {'yes' if s.safe_mode else 'no'}",
        f"  Force direct normal mode: {'yes' if s.force_direct_normal_mode else 'no'}",
        f"  Last subprocess exit code: {s.last_subprocess_exit_code if s.last_subprocess_exit_code is not None else 'n/a'}",
        f"  Last subprocess error: {s.last_subprocess_error or 'n/a'}",
        f"  Playback failure count: {s.playback_failure_count}",
        f"  Last exception: {s.last_exception or 'n/a'}",
        f"  Last success (user-verified only): {'yes' if s.last_success else 'no' if s.last_success is False else 'n/a'}",
        f"  Last provider: {s.last_provider or 'n/a'}",
        f"  Last error: {s.last_error or 'n/a'}",
        f"  Direct engine last completed: {s.direct_engine_last_completed_at or 'n/a'}",
        f"  Direct pyttsx3 user heard: {_fmt_bool(s.direct_pyttsx3_user_heard)}",
        f"  Winsound user heard: {_fmt_bool(s.winsound_user_heard)}",
        f"  WAV+winsound user heard: {_fmt_bool(s.wav_winsound_user_heard)}",
        f"  Sounddevice user heard: {_fmt_bool(s.sounddevice_user_heard)}",
        f"  Last spoken (verified): {s.last_spoken_preview or 'n/a'}",
        f"  Last spoken at (verified): {s.last_spoken_at or 'n/a'}",
        f"  Normal speech path last success: {s.normal_speech_last_success_at or 'n/a'}",
        f"  Last normal speech error: {s.normal_speech_last_error or 'n/a'}",
        f"  Playback audible confirmed: {'yes' if s.playback_audible_confirmed else 'no'}",
        f"  Completion hang detected: {'yes' if s.completion_hang_detected else 'no'}",
        f"  COM recovery mode active: {'yes' if s.com_recovery_mode_active else 'no'}",
        f"  Speech success heuristic active: {'yes' if s.speech_success_heuristic_active else 'no'}",
        f"  Runloop active: {'yes' if s.runloop_active else 'no'}",
        f"  Engine active: {'yes' if s.engine_active else 'no'}",
        f"  Speech lock held: {'yes' if s.speech_lock_held else 'no'}",
        f"  Delayed completion recovered: {'yes' if s.delayed_completion_recovered else 'no'}",
        f"  Completion grace active: {'yes' if s.completion_grace_active else 'no'}",
        f"  Worker grace elapsed ms: {f'{s.worker_grace_elapsed_ms:.0f}' if s.worker_grace_elapsed_ms is not None else 'n/a'}",
        f"  Completion pipeline version: {s.completion_pipeline_version}",
        f"  Grace recovery enabled: {'yes' if s.grace_recovery_enabled else 'no'}",
        f"  Active completion handler: {s.active_completion_handler}",
        f"  Legacy path detected: {'yes' if s.legacy_completion_path_detected else 'no'}",
        f"  Debug force enabled: {'yes' if s.debug_force_enabled else 'no'}",
    ]
    if s.stable_normal_equals_direct is None:
        lines.append("  Stable normal path equals direct: n/a")
    else:
        lines.append(
            f"  Stable normal path equals direct: {'yes' if s.stable_normal_equals_direct else 'no'}"
        )
    if s.startup_self_test:
        lines.append(f"  Startup self-test: {s.startup_self_test}")
    return "\n".join(lines)


def _fmt_bool(val: bool | None) -> str:
    if val is True:
        return "yes"
    if val is False:
        return "no"
    return "n/a"


def reset_audio_status() -> None:
    global _last_spoken_preview, _last_spoken_at, _fallback_active, _startup_self_test
    global _direct_last_success_at, _normal_last_success_at, _normal_last_error, _normal_last_path
    global _direct_pyttsx3_user_heard, _winsound_user_heard, _wav_winsound_user_heard
    global _sounddevice_user_heard, _selected_verified_audio_backend, _force_direct_normal_mode
    global _direct_engine_last_completed_at, _last_subprocess_exit_code, _last_subprocess_error
    global _last_timeout_kill_reason
    global _completion_hang_detected, _com_recovery_mode_active, _speech_success_heuristic_active
    global _delayed_completion_recovered, _completion_grace_active, _worker_grace_elapsed_ms
    global _completion_pipeline_version, _grace_recovery_enabled, _active_completion_handler
    global _legacy_completion_path_detected
    global _debug_force_enabled, _debug_force_applied
    _last_spoken_preview = ""
    _last_spoken_at = None
    _fallback_active = False
    _startup_self_test = None
    _direct_last_success_at = None
    _normal_last_success_at = None
    _normal_last_error = None
    _normal_last_path = None
    _direct_pyttsx3_user_heard = None
    _winsound_user_heard = None
    _wav_winsound_user_heard = None
    _sounddevice_user_heard = None
    _selected_verified_audio_backend = None
    _force_direct_normal_mode = False
    _direct_engine_last_completed_at = None
    _last_subprocess_exit_code = None
    _last_subprocess_error = None
    _last_timeout_kill_reason = None
    _completion_hang_detected = False
    _com_recovery_mode_active = False
    _speech_success_heuristic_active = False
    _delayed_completion_recovered = False
    _completion_grace_active = False
    _worker_grace_elapsed_ms = None
    _completion_pipeline_version = "unknown"
    _grace_recovery_enabled = False
    _active_completion_handler = "unknown"
    _legacy_completion_path_detected = True
    _debug_force_enabled = False
    _debug_force_applied = False
    try:
        from voice.pyttsx3_completion import reset_completion_hang_tracking

        reset_completion_hang_tracking()
    except Exception:
        pass
    try:
        from voice.pyttsx3_lifecycle import reset_pyttsx3_lifecycle_for_tests

        reset_pyttsx3_lifecycle_for_tests()
    except Exception:
        pass
