"""Environment variable precedence: process env > .env > code defaults (Phase 58.1)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CRITICAL_REALTIME_FLAGS: tuple[str, ...] = (
    "VOICE_RUNTIME_MODE",
    "REALTIME_TTS_ENABLED",
    "TTS_SAFE_MODE",
    "ELEVENLABS_WEBSOCKET_ENABLED",
    "REALTIME_FULL_DUPLEX_ENABLED",
    "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED",
    "TOOL_FIRST_MODE",
    "STT_STREAMING_BUFFER_ENABLED",
    "TTS_ENABLED",
)

_process_env_before_dotenv: dict[str, str] = {}
_dotenv_file_values: dict[str, str | None] = {}
_resolved_env: dict[str, tuple[str, str]] = {}
_env_loaded = False


def load_project_env(env_path: Path) -> None:
    """Load .env without overwriting variables already set in the process environment."""
    global _process_env_before_dotenv, _dotenv_file_values, _resolved_env, _env_loaded
    from dotenv import dotenv_values, load_dotenv

    _process_env_before_dotenv = {
        key: os.environ[key] for key in CRITICAL_REALTIME_FLAGS if key in os.environ
    }

    if env_path.is_file():
        _dotenv_file_values = dict(dotenv_values(env_path) or {})
        load_dotenv(env_path, override=False)
    else:
        _dotenv_file_values = {}

    for key, value in _process_env_before_dotenv.items():
        os.environ[key] = value

    _resolved_env = {key: _resolve_key(key) for key in CRITICAL_REALTIME_FLAGS}
    _env_loaded = True


def was_loaded() -> bool:
    return _env_loaded


def process_env_snapshot() -> dict[str, str]:
    return dict(_process_env_before_dotenv)


def get_env_resolution(key: str) -> tuple[str, str]:
    if key in _resolved_env:
        return _resolved_env[key]
    return _resolve_key(key)


def _resolve_key(key: str) -> tuple[str, str]:
    if key in _process_env_before_dotenv:
        return _process_env_before_dotenv[key], "process_env"
    file_val = _dotenv_file_values.get(key)
    if file_val is not None and str(file_val).strip() != "":
        return str(file_val), "dotenv"
    if key in os.environ:
        return os.environ[key], "process_env"
    return "", "default"


def _final_config_value(key: str) -> Any:
    try:
        import config as cfg

        if hasattr(cfg, key):
            return getattr(cfg, key)
    except Exception:
        pass
    raw, _source = get_env_resolution(key)
    if key in {
        "REALTIME_TTS_ENABLED",
        "TTS_SAFE_MODE",
        "ELEVENLABS_WEBSOCKET_ENABLED",
        "REALTIME_FULL_DUPLEX_ENABLED",
        "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED",
        "TOOL_FIRST_MODE",
        "STT_STREAMING_BUFFER_ENABLED",
        "TTS_ENABLED",
    }:
        if not raw:
            return None
        return raw.lower() in {"1", "true", "yes"}
    return raw or None


def format_runtime_config_sources(*, include_final: bool = True) -> str:
    lines = [
        "Runtime config sources (Phase 58.1):",
        "Precedence: process_env > dotenv > default",
        "",
    ]
    for key in CRITICAL_REALTIME_FLAGS:
        raw, source = get_env_resolution(key)
        display = raw if raw else "(unset)"
        line = f"  {key}: source={source} env={display!r}"
        if include_final:
            final = _final_config_value(key)
            if final is not None:
                line += f" final={final!r}"
        lines.append(line)

    mode_raw, mode_source = get_env_resolution("VOICE_RUNTIME_MODE")
    stable_final = _final_config_value("VOICE_RUNTIME_STABLE")
    lines.append(
        "  VOICE_RUNTIME_STABLE: "
        f"source=derived(from VOICE_RUNTIME_MODE={mode_raw!r}/{mode_source}) "
        f"final={stable_final!r}"
    )
    return "\n".join(lines)


def collect_runtime_config_mismatches() -> list[str]:
    """Collect mismatches between env-requested flags and final runtime config."""
    issues: list[str] = []
    mode_raw, mode_source = get_env_resolution("VOICE_RUNTIME_MODE")
    mode = (mode_raw or "").strip().lower()
    stt_raw, stt_source = get_env_resolution("STT_STREAMING_BUFFER_ENABLED")
    stt_requested = (stt_raw or "").strip().lower()

    try:
        import config as cfg

        resolved_mode = (getattr(cfg, "VOICE_RUNTIME_MODE", "") or "").strip().lower()
        resolved_streaming = bool(getattr(cfg, "STT_STREAMING_BUFFER_ENABLED", False))
    except Exception as exc:
        return [f"runtime mismatch check failed: {exc}"]

    if mode and resolved_mode and mode != resolved_mode:
        issues.append(
            "VOICE_RUNTIME_MODE mismatch: "
            f"env={mode!r} ({mode_source}) final={resolved_mode!r}"
        )

    if stt_requested in {"1", "true", "yes"} and not resolved_streaming:
        why = ""
        if resolved_mode == "stable":
            why = " (forced off by stable mode override)"
        issues.append(
            "STT_STREAMING_BUFFER_ENABLED mismatch: "
            f"env={stt_raw!r} ({stt_source}) final={resolved_streaming!r}{why}"
        )
    if stt_requested in {"0", "false", "no"} and resolved_streaming:
        why = ""
        if resolved_mode in {"realtime_experimental", "realtime"}:
            why = " (forced on by realtime_experimental override)"
        issues.append(
            "STT_STREAMING_BUFFER_ENABLED mismatch: "
            f"env={stt_raw!r} ({stt_source}) final={resolved_streaming!r}{why}"
        )
    return issues


def format_runtime_config_mismatches() -> str:
    lines = ["Runtime config mismatches:"]
    mismatches = collect_runtime_config_mismatches()
    if not mismatches:
        lines.append("  none")
        return "\n".join(lines)
    for msg in mismatches:
        lines.append(f"  - {msg}")
    return "\n".join(lines)


def collect_realtime_precedence_warnings() -> list[str]:
    warnings: list[str] = []
    requested = (_process_env_before_dotenv.get("VOICE_RUNTIME_MODE") or "").strip().lower()
    if not requested:
        requested = (get_env_resolution("VOICE_RUNTIME_MODE")[0] or "").strip().lower()
    if requested != "realtime_experimental":
        return warnings

    if "VOICE_RUNTIME_MODE" in _process_env_before_dotenv:
        expected = _process_env_before_dotenv["VOICE_RUNTIME_MODE"]
        current = os.environ.get("VOICE_RUNTIME_MODE", "")
        if current != expected:
            warnings.append(
                "VOICE_RUNTIME_MODE process env was overwritten by later loading: "
                f"expected {expected!r}, got {current!r}"
            )

    try:
        import config as cfg

        if getattr(cfg, "VOICE_RUNTIME_STABLE", False):
            warnings.append(
                "VOICE_RUNTIME_MODE=realtime_experimental but resolved VOICE_RUNTIME_STABLE=True"
            )
        if not getattr(cfg, "REALTIME_TTS_ENABLED", False):
            warnings.append(
                "VOICE_RUNTIME_MODE=realtime_experimental but REALTIME_TTS_ENABLED=False"
            )
        if getattr(cfg, "TTS_SAFE_MODE", True):
            warnings.append(
                "VOICE_RUNTIME_MODE=realtime_experimental but TTS_SAFE_MODE=True"
            )
        resolved_mode = (getattr(cfg, "VOICE_RUNTIME_MODE", "") or "").strip().lower()
        if resolved_mode == "stable":
            warnings.append(
                "VOICE_RUNTIME_MODE=realtime_experimental but cfg.VOICE_RUNTIME_MODE=stable"
            )
    except Exception as exc:
        warnings.append(f"realtime_experimental precedence check failed: {exc}")

    return warnings


def validate_realtime_experimental_resolution() -> list[str]:
    warnings = collect_realtime_precedence_warnings()
    if not warnings:
        return warnings
    try:
        from core.logger import setup_logger

        logger = setup_logger("jarvis.env_precedence")
        for msg in warnings:
            logger.critical(msg)
    except Exception:
        pass
    return warnings


def print_critical_runtime_env_trace() -> None:
    print(format_runtime_config_sources(), flush=True)
    for msg in collect_realtime_precedence_warnings():
        print(f"[CRITICAL] {msg}", flush=True)
    for msg in collect_runtime_config_mismatches():
        print(f"[WARNING] {msg}", flush=True)


def reset_env_precedence_for_tests() -> None:
    global _process_env_before_dotenv, _dotenv_file_values, _resolved_env, _env_loaded
    _process_env_before_dotenv = {}
    _dotenv_file_values = {}
    _resolved_env = {}
    _env_loaded = False
