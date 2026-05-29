"""Entry point for local_jarvis."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="local_jarvis — safe Windows assistant")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--voice", action="store_true", help="Push-to-talk voice mode")
    mode.add_argument("--text", action="store_true", help="Text console mode")
    tray = parser.add_mutually_exclusive_group()
    tray.add_argument("--tray", action="store_true", help="System tray background mode")
    tray.add_argument("--no-tray", action="store_true", help="Disable tray")
    parser.add_argument("--hotkey", action="store_true", help="Voice: SPACE hotkey toggle")
    tts = parser.add_mutually_exclusive_group()
    tts.add_argument("--speak", action="store_true", help="Enable TTS")
    tts.add_argument("--no-speak", action="store_true", help="Disable TTS")
    wake = parser.add_mutually_exclusive_group()
    wake.add_argument("--wakeword", action="store_true", help="Enable wake word listener")
    wake.add_argument("--no-wakeword", action="store_true", help="Disable wake word")
    parser.add_argument(
        "--debug-startup",
        action="store_true",
        help="Print detailed startup / thread diagnostics",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run startup smoke checks and exit",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Minimal text loop only (no tray/voice/wakeword/TTS/watchdog)",
    )
    overlay = parser.add_mutually_exclusive_group()
    overlay.add_argument(
        "--overlay",
        action="store_true",
        help="Enable visual overlay for this run (even if OVERLAY_ENABLED=false)",
    )
    overlay.add_argument(
        "--no-overlay",
        action="store_true",
        help="Disable visual overlay for this run",
    )
    return parser


def _resolve_voice_flag(args: argparse.Namespace) -> tuple[bool, bool]:
    if getattr(args, "safe_mode", False):
        return False, False
    if getattr(args, "voice", False):
        return True, True
    from config import VOICE_ENABLED

    return VOICE_ENABLED, False


def _resolve_wake_flag(args: argparse.Namespace) -> tuple[bool, bool]:
    if getattr(args, "safe_mode", False):
        return False, False
    if getattr(args, "no_wakeword", False):
        return False, False
    if getattr(args, "wakeword", False):
        return True, True
    from config import WAKE_WORD_ENABLED

    return WAKE_WORD_ENABLED, False


def _resolve_overlay_flag(args: argparse.Namespace) -> tuple[bool, bool]:
    """Return (enabled_for_run, cli_override_applied)."""
    if getattr(args, "safe_mode", False):
        return False, False
    if getattr(args, "no_overlay", False):
        return False, True
    if getattr(args, "overlay", False):
        return True, True
    from config import OVERLAY_ENABLED

    return OVERLAY_ENABLED, False


def _resolve_speak_flag(args: argparse.Namespace) -> bool | None:
    if getattr(args, "safe_mode", False):
        return False
    if getattr(args, "speak", False):
        return True
    if getattr(args, "no_speak", False):
        return False
    return None


def _pause_on_error() -> None:
    if not sys.stdin.isatty():
        return
    try:
        input("Press Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> int:
    from core.startup import (
        StartupError,
        append_startup_log,
        check_env_file,
        is_windows_store_python_stub,
        print_debug_thread_status,
        print_jarvis_startup_header,
        print_startup_banner,
        print_store_stub_help,
        probe_optional_imports,
        run_smoke_test,
    )

    parser = _build_parser()
    args = parser.parse_args()

    print_jarvis_startup_header(args)

    if is_windows_store_python_stub():
        print_store_stub_help()
        append_startup_log("aborted: Windows Store python stub")
        return 2

    check_env_file()

    try:
        from alpha.mode import apply_alpha_runtime_defaults, is_alpha_mode

        apply_alpha_runtime_defaults()
        if is_alpha_mode():
            print("[INFO] ALPHA_MODE enabled — friend & family safe defaults active.\n", flush=True)
    except Exception:
        pass

    try:
        from core.intent_validation import run_startup_intent_validation

        run_startup_intent_validation(strict=True)
    except Exception as exc:
        msg = f"Intent registry validation failed: {exc}"
        print(f"\n[ERROR] {msg}\n", flush=True)
        append_startup_log(msg, exc=exc if isinstance(exc, BaseException) else None)
        return 1

    if args.smoke:
        code = run_smoke_test()
        probe_optional_imports(print_results=False)
        return code

    if args.safe_mode:
        append_startup_log("safe-mode start")
        print("[INFO] Safe mode: text console only (no tray/voice/wakeword/TTS).\n", flush=True)
        try:
            from core.app import JarvisApp
            from core.runtime_state import get_runtime_state

            runtime = get_runtime_state()
            runtime.set_voice(False)
            runtime.set_wake_word(False)
            runtime.set_speak(False)
            app = JarvisApp(speak_enabled=False, runtime=runtime, enable_watchdog=False)
            print_startup_banner(args, runtime=runtime, app=app)
            append_startup_log("safe-mode entering text loop")
            app.run()
            return 0
        except Exception as exc:
            print(f"\n[ERROR] Safe mode failed: {exc}\n", flush=True)
            traceback.print_exc()
            append_startup_log("safe-mode failed", exc=exc)
            return 1

    voice_enabled, voice_cli = _resolve_voice_flag(args)
    wake_enabled, wake_cli = _resolve_wake_flag(args)
    tray_app = None

    try:
        print("[INFO] Probing optional imports...", flush=True)
        probe_optional_imports(print_results=True)

        from config import RUNTIME_MONITOR_ENABLED, VOICE_ENABLED, WAKE_WORD_ENABLED
        from core.app import JarvisApp
        from core.logger import setup_logger
        from core.runtime_state import get_runtime_state
        from core.startup import print_runtime_config_flags
        from voice.tts import resolve_tts_enabled

        logger = setup_logger("jarvis.main")
        runtime = get_runtime_state()
        if RUNTIME_MONITOR_ENABLED:
            try:
                from services.runtime_monitor import get_runtime_monitor

                get_runtime_monitor().start()
            except Exception as exc:
                logger.debug("Runtime monitor start failed: %s", exc)
        try:
            from services.high_performance_runtime import get_high_performance_runtime

            get_high_performance_runtime().start()
        except Exception as exc:
            logger.debug("High-performance runtime start failed: %s", exc)

        print_runtime_config_flags()
        if args.debug_startup:
            from voice.performance_status import print_voice_performance_flags

            print_voice_performance_flags()

        if voice_enabled or wake_enabled:
            from voice.transcriber import preload_stt_model, print_stt_startup_info

            print_stt_startup_info()
            preload_stt_model()

        runtime.set_voice(voice_enabled)
        runtime.set_wake_word(wake_enabled)

        speak_flag = _resolve_speak_flag(args)
        resolved_speak = resolve_tts_enabled(speak_flag)
        runtime.set_speak(resolved_speak)
        overlay_enabled, overlay_cli = _resolve_overlay_flag(args)
        use_tray = args.tray and not args.no_tray
        from config import BACKGROUND_MODE, OVERLAY_SHOW_ON_WAKE

        if BACKGROUND_MODE and use_tray:
            overlay_enabled = overlay_enabled or OVERLAY_SHOW_ON_WAKE or True
        runtime.set_overlay(overlay_enabled)
        app = JarvisApp(speak_enabled=resolved_speak, runtime=runtime)

        if not getattr(args, "safe_mode", False):
            try:
                from services.watchdog_runtime import ensure_process_watchdog

                ensure_process_watchdog(runtime=runtime)
            except Exception as exc:
                print(f"[WARNING] Watchdog failed to start: {exc}", flush=True)
                append_startup_log("watchdog failed", exc=exc)

        if resolved_speak:
            try:
                from voice.tts_startup import run_tts_startup_self_test

                run_tts_startup_self_test(enabled=True)
            except Exception as exc:
                print(f"[WARNING] TTS startup self-test skipped: {exc}", flush=True)

        try:
            if BACKGROUND_MODE and use_tray:
                from ui.overlay_app import start_overlay_background

                start_overlay_background(runtime)
            else:
                from ui.overlay_app import start_overlay

                start_overlay(runtime, force=overlay_cli and overlay_enabled)
            if args.debug_startup:
                from ui.overlay_app import get_overlay_controller

                ctrl = get_overlay_controller()
                print(
                    f"Overlay: config={overlay_enabled} runtime={runtime.overlay_enabled} "
                    f"controller={ctrl.is_enabled()} thread="
                    f"{getattr(ctrl._qt_thread, 'is_alive', lambda: False)() if ctrl._qt_thread else False}",
                    flush=True,
                )
        except Exception as exc:
            print(f"[WARNING] Overlay startup skipped: {exc}", flush=True)
            append_startup_log("overlay startup skipped", exc=exc)

        print_startup_banner(
            args,
            runtime=runtime,
            app=app,
            voice_cli_override=voice_cli and not VOICE_ENABLED,
            wake_cli_override=wake_cli and not WAKE_WORD_ENABLED,
            speak_cli_override=speak_flag is not None,
            overlay_cli_override=overlay_cli,
        )
        append_startup_log(
            "startup",
            extra={
                "mode": "tray" if args.tray else "other",
                "wake": runtime.wake_word_enabled,
                "voice": runtime.voice_enabled,
                "speak": app.speak_enabled,
                "python": sys.executable,
            },
        )

        if use_tray:
            from ui.tray_app import JarvisTrayApp

            if voice_cli:
                print("Voice enabled by CLI flag.", flush=True)
            if wake_cli:
                print("Wake word enabled by CLI flag.", flush=True)
            if runtime.wake_word_enabled:
                from voice.wakeword import print_wake_word_model_status

                res = print_wake_word_model_status()
                if not res.ok:
                    runtime.set_wake_word(False)
                    print(
                        "[WARNING] Wake word disabled — model missing. "
                        "Voice/tray otherwise continue.",
                        flush=True,
                    )
                else:
                    print("Wake word listener starting…", flush=True)
                    from voice.wake_phrases import wake_listen_prompt

                    print(wake_listen_prompt(), flush=True)

            from config import BACKGROUND_MODE, START_MINIMIZED

            if BACKGROUND_MODE or START_MINIMIZED:
                append_startup_log("background quiet mode: tray only (no console HUD)")
                if BACKGROUND_MODE:
                    print(
                        "[INFO] Background quiet mode — tray + wake word; overlay hidden until wake/command.",
                        flush=True,
                    )
            tray_app = JarvisTrayApp(
                app,
                start_voice_thread=runtime.voice_enabled,
                start_wakeword_thread=runtime.wake_word_enabled,
                enable_watchdog=True,
            )
            if args.debug_startup and runtime.wake_word_enabled:
                from voice.wakeword import print_wake_word_model_status

                print_wake_word_model_status()
            print("Entering tray main loop (blocking until tray exits).", flush=True)
            append_startup_log("tray: entering main loop")
            logger.info("Entering tray main loop (blocking)")
            tray_app.start(debug_startup=args.debug_startup)
            print("Tray exited.", flush=True)
            append_startup_log("tray: main loop ended")
        elif args.voice:
            from voice.voice_loop import run_voice_loop

            append_startup_log("voice loop start")
            run_voice_loop(app, hotkey=args.hotkey, runtime=runtime)
        elif runtime.wake_word_enabled:
            from voice.wakeword_loop import start_wakeword_loop, stop_wakeword_loop

            print("Wake word listener started", flush=True)
            from voice.wake_phrases import wake_listen_prompt

            print(wake_listen_prompt(), flush=True)
            append_startup_log("wakeword-only: detector starting")
            detector = start_wakeword_loop(app)
            try:
                from ui.operator_console import start_operator_console

                start_operator_console(app)
            except Exception as exc:
                print(f"[WARNING] Operator console skipped: {exc}", flush=True)
            append_startup_log("wakeword-only: keepalive loop")
            try:
                import time

                while app._running and runtime.running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\nStopping…", flush=True)
            finally:
                stop_wakeword_loop(detector)
                append_startup_log("wakeword-only: stopped")
        else:
            append_startup_log("text mode start")
            app.run()

        return 0

    except StartupError as exc:
        msg = f"Startup failed: {exc}"
        print(f"\n[ERROR] {msg}\n", flush=True)
        traceback.print_exc()
        append_startup_log(msg, exc=exc)
        return 1
    except Exception as exc:
        msg = f"Fatal startup error: {exc}"
        print(f"\n[ERROR] {msg}\n", flush=True)
        traceback.print_exc()
        append_startup_log(msg, exc=exc)
        if args.debug_startup and tray_app is not None:
            print_debug_thread_status(tray_app)
        return 1
    finally:
        try:
            from memory.session_memory import persist_session_summary

            persist_session_summary()
        except Exception:
            pass
        try:
            from services.runtime_monitor import get_runtime_monitor

            get_runtime_monitor().stop()
        except Exception:
            pass
        try:
            from services.high_performance_runtime import get_high_performance_runtime

            get_high_performance_runtime().stop()
        except Exception:
            pass


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except SystemExit as exc:
        code = exc.code
        exit_code = int(code) if isinstance(code, int) else (0 if code is None else 1)
    except BaseException:
        traceback.print_exc()
        try:
            from core.startup import append_startup_log

            append_startup_log("unhandled exception in __main__", exc=sys.exc_info()[1])
        except Exception:
            pass
        _pause_on_error()
        exit_code = 1
    else:
        if exit_code != 0:
            _pause_on_error()
    raise SystemExit(exit_code)
