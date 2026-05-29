"""Unified JARVIS runtime bootstrap — env, speak, conversational voice (Phase 59.3)."""

from __future__ import annotations

import os
from typing import Any

from core.logger import setup_logger
from core.runtime_state import RuntimeState, get_runtime_state

logger = setup_logger("jarvis.runtime_bootstrap")

_bootstrapped = False
_diagnostics_printed = False

STARTUP_ENV_KEYS: tuple[str, ...] = (
    "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED",
    "TOOL_FIRST_MODE",
    "VOICE_RUNTIME_MODE",
    "TTS_SAFE_MODE",
    "STT_STREAMING_BUFFER_ENABLED",
    "TTS_ENABLED",
    "REALTIME_TTS_ENABLED",
)


def is_runtime_bootstrapped() -> bool:
    return _bootstrapped


def ensure_jarvis_runtime_bootstrapped(
    *,
    runtime: RuntimeState | None = None,
    speak_enabled: bool | None = None,
    enable_watchdog: bool = True,
) -> RuntimeState:
    """
    Idempotent startup path shared by main() and JarvisApp().

    Applies audio/conversational runtime init and syncs speak_enabled from config
    when the caller did not pass an explicit override.
    """
    global _bootstrapped
    runtime = runtime or get_runtime_state()

    if not _bootstrapped:
        # One-time backup cleanup (VF-1): trim data/backups/ to 5 files per stem.
        try:
            from core.persistent_json import cleanup_old_backups
            from config import DATA_DIR

            removed = cleanup_old_backups(DATA_DIR / "backups")
            if removed:
                logger.info("Startup: removed %d stale backup files from data/backups/", removed)
        except Exception as exc:
            logger.debug("Startup backup cleanup skipped: %s", exc)

        # S2.5 / S3.2 — config + optional dependency checks (degraded, not fatal).
        try:
            from core.startup_validation import (
                apply_startup_validation_to_runtime,
                run_startup_validation,
            )

            validation = run_startup_validation()
            apply_startup_validation_to_runtime(runtime, validation, print_summary=True)
        except Exception as exc:
            logger.debug("Startup validation skipped: %s", exc)

        try:
            from voice.audio_runtime_init import initialize_audio_runtime_at_startup

            initialize_audio_runtime_at_startup()
        except Exception as exc:
            logger.warning("Audio runtime bootstrap failed: %s", exc)

        # S3.1 — build 11-agent registry and run health checks.
        try:
            from agents.registry import build_default_registry, validate_registry
            build_default_registry()
            errors = validate_registry()
            if errors:
                logger.warning("AgentRegistry: %d unhealthy agent(s) at startup", len(errors))
        except Exception as exc:
            logger.warning("Agent registry bootstrap failed: %s", exc)

        # S3.5 — start HealthMonitorAgent heartbeat (30s storage checks).
        try:
            from agents.health_monitor_agent import get_health_monitor_agent
            get_health_monitor_agent().start()
        except Exception as exc:
            logger.warning("HealthMonitorAgent start failed: %s", exc)

        # Phase 78 — build + validate the Tool Registry catalog at startup.
        # ADDITIVE ONLY: this changes no routing. The keyword classifier and
        # ActionRegistry remain authoritative. LLM tool routing stays disabled.
        try:
            from tools.flags import llm_tool_router_enabled, tool_registry_enabled

            if tool_registry_enabled():
                from tools.catalog import build_default_tool_registry

                treg = build_default_tool_registry()
                logger.info(
                    "ToolRegistry: %d tools registered (%s); llm_tool_router=%s",
                    len(treg.all()), treg.by_safety_class(),
                    "on" if llm_tool_router_enabled() else "off",
                )
        except Exception as exc:
            logger.warning("ToolRegistry build skipped: %s", exc)

        if enable_watchdog:
            try:
                from services.watchdog_runtime import ensure_process_watchdog

                ensure_process_watchdog(runtime=runtime)
            except Exception as exc:
                logger.warning("Process watchdog start failed: %s", exc)

        _bootstrapped = True

    from voice.tts import resolve_tts_enabled

    if speak_enabled is not None:
        runtime.set_speak(speak_enabled)
    else:
        runtime.set_speak(resolve_tts_enabled(None))

    return runtime


def _config_flag(name: str, default: Any = "") -> Any:
    try:
        import config as cfg

        return getattr(cfg, name, default)
    except Exception:
        return default


def _selected_tts_backend() -> str:
    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        return audio.active_backend or audio.selected_verified_audio_backend or "none"
    except Exception:
        return "unknown"


def format_jarvis_runtime_diagnostics(*, runtime: RuntimeState | None = None) -> str:
    runtime = runtime or get_runtime_state()
    try:
        from conversation.human_runtime import (
            is_human_conversational_runtime_enabled,
            uses_continuous_conversation,
        )
        from voice.tts_output_policy import evaluate_tts_output

        decision = evaluate_tts_output(
            speak_enabled=runtime.speak_enabled,
            voice_path="startup_diagnostics",
        )
    except Exception as exc:
        decision = None
        conv_enabled = False
        continuous_mic = False
        diag_exc = str(exc)
    else:
        conv_enabled = is_human_conversational_runtime_enabled()
        continuous_mic = uses_continuous_conversation()
        diag_exc = ""

    lines = [
        "JARVIS runtime bootstrap diagnostics:",
        f"  bootstrap applied: {'yes' if _bootstrapped else 'no'}",
        f"  speak_enabled: {'yes' if runtime.speak_enabled else 'no'}",
        f"  muted: {'yes' if not runtime.speak_enabled else 'no'}",
    ]
    if decision is not None:
        lines.extend(
            [
                f"  audio_mode: {decision.audio_mode}",
                f"  tts policy reason: {decision.reason}",
                f"  overlay_status: {decision.overlay_status or 'n/a'}",
            ]
        )
    elif diag_exc:
        lines.append(f"  tts policy: unavailable ({diag_exc})")

    lines.extend(
        [
            f"  VOICE_RUNTIME_MODE: {_config_flag('VOICE_RUNTIME_MODE', '')}",
            f"  VOICE_RUNTIME_STABLE: {_config_flag('VOICE_RUNTIME_STABLE', False)}",
            f"  conversational runtime enabled: {'yes' if conv_enabled else 'no'}",
            f"  continuous mic: {'yes' if continuous_mic else 'no'}",
            f"  selected TTS backend: {_selected_tts_backend()}",
            "",
            "Resolved env (process vs config):",
        ]
    )
    for key in STARTUP_ENV_KEYS:
        process_val = os.environ.get(key, "(unset)")
        cfg_val = _config_flag(key, "(n/a)")
        lines.append(f"  {key}: process={process_val!r} config={cfg_val!r}")

    return "\n".join(lines)


def print_jarvis_runtime_diagnostics(*, runtime: RuntimeState | None = None) -> None:
    global _diagnostics_printed
    if _diagnostics_printed:
        return
    print(format_jarvis_runtime_diagnostics(runtime=runtime), flush=True)
    try:
        from core.env_precedence import collect_runtime_config_mismatches

        for msg in collect_runtime_config_mismatches():
            print(f"[WARNING] runtime config mismatch: {msg}", flush=True)
    except Exception:
        pass
    print("", flush=True)
    _diagnostics_printed = True


def format_show_tts_debug(*, runtime: RuntimeState | None = None) -> str:
    runtime = runtime or get_runtime_state()
    from conversation.human_runtime import (
        get_session_snapshot,
        is_human_conversational_runtime_enabled,
        uses_continuous_conversation,
    )
    from voice.audio_status import get_audio_status
    from voice.backend_verification import (
        format_backend_verification_diagnostics,
        is_backend_initialized,
    )
    from voice.tool_first_mode import is_tool_first_mode
    from voice.playback_metrics import format_playback_metrics
    from voice.tts_output_policy import evaluate_tts_output, format_tts_output_diagnostics

    decision = evaluate_tts_output(
        speak_enabled=runtime.speak_enabled,
        voice_path="show_tts_debug",
    )
    audio = get_audio_status()
    snap = get_session_snapshot()
    backend = audio.active_backend or "none"
    verified = audio.selected_verified_audio_backend or "none"

    lines = [
        "TTS debug:",
        f"  speak_enabled: {'yes' if runtime.speak_enabled else 'no'}",
        f"  muted: {'yes' if not runtime.speak_enabled else 'no'}",
        f"  audio_mode: {decision.audio_mode}",
        f"  backend: {backend}",
        f"  verified backend: {verified}",
        f"  backend initialized: {'yes' if is_backend_initialized() else 'no'}",
        f"  last suppression reason: {decision.reason}",
        f"  session active: {'yes' if snap.get('session_active') else 'no'}",
        f"  tool_first_mode: {'yes' if is_tool_first_mode() else 'no'}",
        f"  conversational runtime enabled: {'yes' if is_human_conversational_runtime_enabled() else 'no'}",
        f"  continuous mic: {'yes' if uses_continuous_conversation() else 'no'}",
        f"  bootstrap applied: {'yes' if _bootstrapped else 'no'}",
        "",
        format_tts_output_diagnostics(),
        "",
        format_backend_verification_diagnostics(),
        "",
        format_playback_metrics(),
        "",
        format_jarvis_runtime_diagnostics(runtime=runtime),
    ]
    return "\n".join(lines)


def reset_runtime_bootstrap_for_tests() -> None:
    global _bootstrapped, _diagnostics_printed
    _bootstrapped = False
    _diagnostics_printed = False
