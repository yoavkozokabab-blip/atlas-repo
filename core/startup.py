"""Startup diagnostics, logging, smoke checks, and crash protection."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
STARTUP_LOG_DIR = PROJECT_ROOT / "reports" / "jarvis_logs"
STARTUP_LATEST_LOG = STARTUP_LOG_DIR / "startup_latest.log"

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "token",
        "password",
        "secret",
        "openai",
        "telegram",
        "bearer",
    }
)

OPTIONAL_IMPORTS: tuple[tuple[str, str], ...] = (
    ("pystray", "pystray"),
    ("Pillow", "PIL"),
    ("openwakeword", "openwakeword"),
    ("onnxruntime", "onnxruntime"),
    ("sounddevice", "sounddevice"),
    ("pyttsx3", "pyttsx3"),
    ("PySide6", "PySide6"),
)


class StartupError(Exception):
    """Fatal startup failure."""


def append_startup_log(
    message: str,
    *,
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append to dated log and always refresh startup_latest.log tail."""
    STARTUP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    dated_path = STARTUP_LOG_DIR / f"startup_{stamp}.log"
    ts = datetime.now(timezone.utc).isoformat()
    block = [f"[{ts}] {message}\n"]
    if extra:
        for k, v in extra.items():
            if any(s in str(k).lower() for s in _SECRET_KEYS):
                v = "[redacted]"
            block.append(f"  {k}={v}\n")
    if exc is not None:
        block.append(traceback.format_exc())
        block.append("\n")

    payload = "".join(block)
    for path in (dated_path, STARTUP_LATEST_LOG):
        with path.open("a", encoding="utf-8") as f:
            f.write(payload)
    return STARTUP_LATEST_LOG


def is_windows_store_python_stub() -> bool:
    """True if `python` is likely the Windows Store alias (prints 'Python' and exits)."""
    exe = Path(sys.executable)
    exe_str = str(exe).lower()
    if "windowsapps" in exe_str and exe.name.lower() in {"python.exe", "python3.exe"}:
        return True
    if os.environ.get("PYTHONEXECUTABLE", "").lower().find("windowsapps") >= 0:
        return True
    try:
        import subprocess

        proc = subprocess.run(
            [sys.executable, "-c", "import sys; print(sys.version)"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out or out == "Python":
            return True
    except Exception:
        return True
    return False


def print_store_stub_help() -> None:
    print(
        "\n[ERROR] Windows Store 'python' stub detected — JARVIS did not start.\n"
        "The stub prints only 'Python' and exits. Use a real interpreter:\n"
        "  py -3 main.py --smoke\n"
        "  py -3 main.py --tray --debug-startup\n"
        "  .venv\\Scripts\\python.exe main.py --smoke\n"
        "Or run:  .\\jarvis.ps1 --smoke\n",
        flush=True,
    )


def print_jarvis_startup_header(args: argparse.Namespace | None = None) -> None:
    """Print banner immediately (no heavy project imports)."""
    mode = describe_modes(args) if args is not None else "unknown"
    env_loaded = ENV_FILE.is_file()
    print("================================", flush=True)
    print("JARVIS STARTUP", flush=True)
    print("================================", flush=True)
    print(f"Python executable: {sys.executable}", flush=True)
    print(f"Python version: {sys.version.split()[0]}", flush=True)
    print(f"Working directory: {Path.cwd()}", flush=True)
    print(f"Project root: {PROJECT_ROOT}", flush=True)
    print(f"Loaded .env: {'yes' if env_loaded else 'no'}", flush=True)
    print(f"Mode: {mode}", flush=True)
    if is_windows_store_python_stub():
        print("[WARNING] Python executable looks like Windows Store stub.", flush=True)
    print("================================", flush=True)
    print("", flush=True)
    append_startup_log(
        "startup header",
        extra={
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "env": "yes" if env_loaded else "no",
            "mode": mode,
        },
    )


def probe_optional_imports(*, print_results: bool = True) -> dict[str, tuple[bool, str]]:
    """Try optional deps individually; never raise."""
    results: dict[str, tuple[bool, str]] = {}
    for label, module in OPTIONAL_IMPORTS:
        try:
            __import__(module)
            results[label] = (True, "ok")
            if print_results:
                print(f"[OK] import {label}", flush=True)
            append_startup_log(f"import {label}: ok")
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            results[label] = (False, msg)
            if print_results:
                print(f"Failed importing {label}: {msg}", flush=True)
            append_startup_log(f"import {label}: FAIL", exc=exc)
    return results


def check_env_file(*, print_warning: bool = True) -> bool:
    if ENV_FILE.is_file():
        return True
    if print_warning and ENV_EXAMPLE.is_file():
        print(
            "\n[WARNING] .env not found. Copy .env.example to .env and edit .env, "
            "not .env.example.\n"
            f"  Expected: {ENV_FILE}\n"
            f"  Run: copy .env.example .env\n",
            flush=True,
        )
    return False


def describe_modes(args: argparse.Namespace) -> str:
    if getattr(args, "safe_mode", False):
        return "safe-mode"
    if getattr(args, "smoke", False):
        return "smoke"
    parts: list[str] = []
    if args.tray and not getattr(args, "no_tray", False):
        parts.append("tray")
    elif args.voice:
        parts.append("voice")
    elif args.text:
        parts.append("text")
    else:
        parts.append("text(default)")
    if args.voice and "voice" not in parts:
        parts.append("voice")
    if getattr(args, "wakeword", False):
        parts.append("wakeword")
    elif not getattr(args, "no_wakeword", False) and _env_wake_enabled():
        parts.append("wakeword(env)")
    if getattr(args, "speak", False):
        parts.append("speak")
    if getattr(args, "no_speak", False):
        parts.append("no-speak")
    if getattr(args, "debug_startup", False):
        parts.append("debug-startup")
    if getattr(args, "overlay", False):
        parts.append("overlay")
    if getattr(args, "no_overlay", False):
        parts.append("no-overlay")
    return "+".join(parts) if parts else "none"


def _env_wake_enabled() -> bool:
    try:
        from config import WAKE_WORD_ENABLED

        return WAKE_WORD_ENABLED
    except Exception:
        return False


def _safe_config_snapshot() -> dict[str, Any]:
    import config

    safe: dict[str, Any] = {}
    for key in dir(config):
        if key.startswith("_") or not key.isupper():
            continue
        val = getattr(config, key)
        key_lower = key.lower()
        if any(s in key_lower for s in ("key", "token", "password", "secret")):
            safe[key] = "[redacted]"
        elif isinstance(val, (str, int, float, bool)) or val is None:
            safe[key] = val
        elif isinstance(val, Path):
            safe[key] = str(val)
        elif isinstance(val, frozenset):
            safe[key] = f"frozenset({len(val)} items)"
    return safe


def print_runtime_config_flags() -> None:
    """Print effective runtime flags for voice/TTS/wake/overlay/STT (after config load)."""
    import config

    print("--- Runtime config ---", flush=True)
    try:
        from core.env_precedence import print_critical_runtime_env_trace

        print_critical_runtime_env_trace()
    except Exception as exc:
        print(f"Runtime config source trace unavailable ({exc})", flush=True)
    try:
        from voice.runtime_mode import format_stable_mode_banner

        print(format_stable_mode_banner(), flush=True)
    except Exception:
        pass
    flags = [
        ("VOICE_RUNTIME_MODE", getattr(config, "VOICE_RUNTIME_MODE", "")),
        ("VOICE_ENABLED", config.VOICE_ENABLED),
        ("TTS_ENABLED", config.TTS_ENABLED),
        ("TTS_ENGINE", config.TTS_ENGINE),
        ("TTS_VOICE", config.TTS_VOICE),
        ("TTS_RATE", config.TTS_RATE_RAW),
        ("TTS_ASYNC", config.TTS_ASYNC),
        ("WAKE_WORD_ENABLED", config.WAKE_WORD_ENABLED),
        ("BACKGROUND_MODE", config.BACKGROUND_MODE),
        ("START_MINIMIZED", config.START_MINIMIZED),
        ("OVERLAY_START_HIDDEN", config.OVERLAY_START_HIDDEN),
        ("OVERLAY_SHOW_ON_WAKE", config.OVERLAY_SHOW_ON_WAKE),
        ("OVERLAY_ENABLED", config.OVERLAY_ENABLED),
        ("OVERLAY_STYLE", config.OVERLAY_STYLE),
        ("WAKE_GREETING_ENABLED", config.WAKE_GREETING_ENABLED),
        ("JARVIS_USER_NAME", config.JARVIS_USER_NAME),
        ("STT_LANGUAGE", config.STT_LANGUAGE),
        ("STT_MODEL", config.STT_MODEL),
        ("STT_ENABLE_NORMALIZATION", config.STT_ENABLE_NORMALIZATION),
        ("OVERLAY_STYLE", config.OVERLAY_STYLE),
    ]
    for key, val in flags:
        print(f"  {key}={val}", flush=True)
    print("-----------------------------", flush=True)
    print("", flush=True)


def print_startup_banner(
    args: argparse.Namespace,
    *,
    runtime: Any | None = None,
    app: Any | None = None,
    voice_cli_override: bool = False,
    wake_cli_override: bool = False,
    speak_cli_override: bool = False,
    overlay_cli_override: bool = False,
) -> None:
    import config

    print_jarvis_startup_header(args)
    lines = [
        f"VOICE_ENABLED (config): {config.VOICE_ENABLED}",
        f"TTS_ENABLED (config): {config.TTS_ENABLED}",
        f"WAKE_WORD_ENABLED (config): {config.WAKE_WORD_ENABLED}",
        f"OVERLAY_ENABLED (config): {config.OVERLAY_ENABLED}",
        f"OVERLAY_STYLE (config): {config.OVERLAY_STYLE}",
        f"TTS (this run): {getattr(app, 'speak_enabled', 'n/a') if app else 'pending'}",
    ]
    if voice_cli_override:
        lines.append("Voice enabled by CLI flag.")
    if wake_cli_override:
        lines.append("Wake word enabled by CLI flag.")
    if speak_cli_override:
        lines.append("TTS overridden by CLI flag (--speak / --no-speak).")
    if overlay_cli_override:
        lines.append("Overlay overridden by CLI flag (--overlay / --no-overlay).")
    if runtime is not None:
        lines.append(
            f"Runtime: voice={runtime.voice_enabled} "
            f"wakeword={runtime.wake_word_enabled} "
            f"speak={runtime.speak_enabled} overlay={runtime.overlay_enabled}"
        )
    for line in lines:
        print(line, flush=True)
    print("", flush=True)


def print_debug_thread_status(tray_app: Any | None = None) -> None:
    print("\n=== debug-startup ===", flush=True)
    try:
        print_runtime_config_flags()
    except Exception as exc:
        print(f"Runtime config flags: unavailable ({exc})", flush=True)
    try:
        from voice.performance_status import print_voice_performance_flags

        print_voice_performance_flags()
    except Exception as exc:
        print(f"Voice performance flags: unavailable ({exc})", flush=True)
    if tray_app is None:
        print("Tray app: not started", flush=True)
        return
    rt = tray_app.runtime
    print(f"tray_enabled: {rt.tray_enabled}", flush=True)
    print(f"voice_enabled: {rt.voice_enabled}", flush=True)
    print(f"wake_word_enabled: {rt.wake_word_enabled}", flush=True)
    vt = getattr(tray_app, "_voice_thread", None)
    print(f"voice thread alive: {vt.is_alive() if vt else False}", flush=True)
    wd = getattr(tray_app, "_wakeword_detector", None)
    wthread = getattr(wd, "_thread", None) if wd else None
    print(f"wakeword thread alive: {wthread.is_alive() if wthread else False}", flush=True)
    wdog = getattr(tray_app, "_watchdog", None)
    wdt = getattr(wdog, "_thread", None) if wdog else None
    print(f"watchdog thread alive: {wdt.is_alive() if wdt else False}", flush=True)
    print(f"overlay_enabled: {getattr(rt, 'overlay_enabled', False)}", flush=True)
    try:
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()
        qt = getattr(ctrl, "_qt_thread", None)
        print(
            f"overlay controller enabled={ctrl.is_enabled()} "
            f"active={ctrl.is_active()} qt_thread_alive={qt.is_alive() if qt else False}",
            flush=True,
        )
    except Exception as exc:
        print(f"overlay status: unavailable ({exc})", flush=True)
    print(f"last_error: {getattr(rt, 'wake_word_last_error', None)}", flush=True)
    print("=====================\n", flush=True)


def _smoke_line(label: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f": {detail}" if detail and detail != "ok" else ""
    print(f"[{status}] {label}{suffix}", flush=True)


def _try_check(label: str, fn: Callable[[], None]) -> tuple[bool, str]:
    try:
        fn()
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run_smoke_test() -> int:
    """
    Startup smoke — always prints [PASS]/[FAIL] lines; never exits silently.
    """
    print("\n=== JARVIS SMOKE TEST ===\n", flush=True)
    append_startup_log("smoke test begin")
    results: list[tuple[str, bool, str]] = []
    all_pass = True

    try:
        if not ENV_FILE.is_file():
            _smoke_line(".env file", False, "missing (copy .env.example to .env)")
            results.append((".env file", False, "missing"))
        else:
            _smoke_line(".env file", True, str(ENV_FILE))
            results.append((".env file", True, "ok"))

        ok, detail = _try_check("config loaded", lambda: __import__("config"))
        _smoke_line("config loaded", ok, detail)
        results.append(("config loaded", ok, detail))
        if not ok:
            all_pass = False

        def _intent_import_smoke() -> None:
            import brain.english_voice_phrases  # noqa: F401
            import brain.intent_classifier  # noqa: F401

        ok, detail = _try_check("classifier modules import", _intent_import_smoke)
        _smoke_line("classifier modules import", ok, detail)
        results.append(("classifier modules import", ok, detail))
        if not ok:
            all_pass = False

        def _intent_registry_smoke() -> None:
            from core.intent_validation import format_validation_report, validate_intent_registry_consistency

            issues = validate_intent_registry_consistency()
            if issues:
                raise RuntimeError(format_validation_report(issues))

        ok, detail = _try_check("intent registry consistency", _intent_registry_smoke)
        _smoke_line("intent registry consistency", ok, detail)
        results.append(("intent registry consistency", ok, detail))
        if not ok:
            all_pass = False

        def _classifier_phrase_smoke() -> None:
            from brain.intent_classifier import classify_rules
            from core.types import Intent

            expected = {
                "run historical validation sweep": Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
                "audit execution path": Intent.AUDIT_EXECUTION_PATH,
                "explain zero execution attempts": Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS,
                "show execution blockers": Intent.SHOW_EXECUTION_BLOCKERS,
                "rank execution block reasons": Intent.RANK_EXECUTION_BLOCK_REASONS,
                "inspect execution adapter": Intent.INSPECT_EXECUTION_ADAPTER,
                "compare signal count to order attempts": Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS,
                "generate execution investigation report": Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT,
            }
            for phrase, intent in expected.items():
                got = classify_rules(phrase)
                if got.intent != intent:
                    raise RuntimeError(f"{phrase!r} -> {got.intent.value}, expected {intent.value}")

        ok, detail = _try_check("phase 46 classifier phrases", _classifier_phrase_smoke)
        _smoke_line("phase 46 classifier phrases", ok, detail)
        results.append(("phase 46 classifier phrases", ok, detail))
        if not ok:
            all_pass = False

        for label, module in (
            ("pystray import", "pystray"),
            ("Pillow import", "PIL"),
            ("PySide6 import", "PySide6"),
            ("openwakeword import", "openwakeword"),
            ("onnxruntime import", "onnxruntime"),
            ("sounddevice import", "sounddevice"),
            ("pyttsx3 import", "pyttsx3"),
        ):
            ok, detail = _try_check(label, lambda m=module: __import__(m))
            _smoke_line(label, ok, detail)
            results.append((label, ok, detail))

        try:
            from voice.wakeword import resolve_wake_word_model

            wake_res = resolve_wake_word_model()
            wake_ok = wake_res.ok
            wake_detail = (
                str(wake_res.model_path)
                if wake_ok
                else (
                    f"{wake_res.error or 'missing'}; "
                    f"searched {len(wake_res.searched_paths)} path(s)"
                )
            )
        except Exception as exc:
            wake_ok = False
            wake_detail = str(exc)
        _smoke_line("wake word model file", wake_ok, wake_detail)
        results.append(("wake word model file", wake_ok, wake_detail))

        ok_sd = next((p for n, p, _d in results if n == "sounddevice import"), False)
        if ok_sd:
            try:
                import sounddevice as sd

                devs = sd.query_devices()
                inputs = sum(
                    1
                    for d in devs
                    if isinstance(d, dict) and d.get("max_input_channels", 0) > 0
                )
                mic_ok = inputs > 0
                detail = f"{inputs} input device(s)"
            except Exception as exc:
                mic_ok = False
                detail = str(exc)
        else:
            mic_ok = False
            detail = "skipped (sounddevice not available)"
        _smoke_line("microphone query", mic_ok, detail)
        results.append(("microphone query", mic_ok, detail))

        try:
            import config

            overlay_default_ok = bool(config.OVERLAY_STYLE)
            overlay_detail = (
                f"OVERLAY_ENABLED={config.OVERLAY_ENABLED} "
                f"style={config.OVERLAY_STYLE} "
                f"theme={config.OVERLAY_THEME} "
                f"opacity={config.OVERLAY_OPACITY}"
            )
        except Exception as exc:
            overlay_default_ok = False
            overlay_detail = str(exc)
        _smoke_line("overlay config", overlay_default_ok, overlay_detail)
        results.append(("overlay config", overlay_default_ok, overlay_detail))

        critical = {"config loaded"}
        for name, passed, _detail in results:
            if name in critical and not passed:
                all_pass = False

        summary = "PASS" if all_pass else "FAIL"
        print(f"\nSmoke overall: {summary}\n", flush=True)
        append_startup_log(
            f"smoke test {summary}",
            extra={n: ("PASS" if p else "FAIL") + f" ({d})" for n, p, d in results},
        )
        return 0 if all_pass else 1
    except Exception as exc:
        print(f"[FAIL] smoke test crashed: {exc}", flush=True)
        traceback.print_exc()
        append_startup_log("smoke test crashed", exc=exc)
        return 1


def reload_env_if_present() -> None:
    """Reload .env without overriding process environment (process env wins)."""
    from core.env_precedence import load_project_env

    load_project_env(ENV_FILE)
