"""Modal stdin ownership — verification prompts vs operator console routing."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.ui.console_modal")

DEFAULT_MODAL_TIMEOUT_SECONDS = 120.0
_MAX_REPROMPTS = 12

_lock = threading.Lock()
_session: "_ModalSession | None" = None


@dataclass
class _ModalSession:
    prompt: str
    deadline: float
    line_ready: threading.Event = field(default_factory=threading.Event)
    pending_line: str | None = None
    reprompts: int = 0


def is_modal_active() -> bool:
    with _lock:
        return _session is not None


def submit_modal_line(text: str) -> bool:
    """Operator console read loop delivers a line to the active modal prompt."""
    with _lock:
        session = _session
        if session is None:
            return False
        stripped = (text or "").strip()
        if not stripped:
            return True
        lower = stripped.lower()
        if lower in {"cancel", "abort", "quit"}:
            session.pending_line = "__cancel__"
        else:
            session.pending_line = stripped
        session.line_ready.set()
    return True


def _release_modal() -> None:
    global _session
    with _lock:
        _session = None


def _operator_console_stdin_shared() -> bool:
    try:
        from ui.operator_console import get_operator_console, should_start_operator_console

        if not should_start_operator_console():
            return False
        return get_operator_console() is not None
    except Exception:
        return False


def run_modal_yes_no_prompt(
    prompt: str,
    *,
    timeout_seconds: float = DEFAULT_MODAL_TIMEOUT_SECONDS,
    input_fn: Callable[[str], str] | None = None,
) -> bool | None:
    """
    Block until yes/no (or cancel/timeout). Uses operator-console stdin when running.
    """
    from voice.audio_route_prove import parse_yes_no

    if input_fn is not None:
        return _run_modal_with_input_fn(prompt, input_fn, parse_yes_no)

    if not _operator_console_stdin_shared():
        if sys.stdin.isatty():
            return _run_modal_with_input_fn(prompt, input, parse_yes_no)
        return None

    if not _try_acquire_modal(prompt, timeout_seconds):
        print("[CONSOLE_MODAL] nested prompt blocked", flush=True)
        return None

    print("[CONSOLE_MODAL] acquire", flush=True)
    print(prompt, flush=True)
    try:
        while True:
            with _lock:
                session = _session
            if session is None:
                return None

            remaining = session.deadline - time.monotonic()
            if remaining <= 0:
                print("[CONSOLE_MODAL] timeout", flush=True)
                return None

            if not session.line_ready.wait(timeout=min(1.0, remaining)):
                continue

            with _lock:
                line = session.pending_line
                session.pending_line = None
                session.line_ready.clear()

            if line == "__cancel__":
                print("[CONSOLE_MODAL] cancel", flush=True)
                return None

            parsed = parse_yes_no(line or "")
            if parsed is not None:
                label = "yes" if parsed else "no"
                print(f"[CONSOLE_MODAL] answer={label}", flush=True)
                return parsed

            with _lock:
                if _session is not None:
                    _session.reprompts += 1
                    if _session.reprompts >= _MAX_REPROMPTS:
                        print("[CONSOLE_MODAL] max reprompts", flush=True)
                        return None
            print("Please answer yes or no (or cancel).", flush=True)
    finally:
        _release_modal()
        print("[CONSOLE_MODAL] release", flush=True)


def _try_acquire_modal(prompt: str, timeout_seconds: float) -> bool:
    global _session
    with _lock:
        if _session is not None:
            return False
        _session = _ModalSession(
            prompt=prompt,
            deadline=time.monotonic() + max(5.0, float(timeout_seconds)),
        )
        return True


def _run_modal_with_input_fn(
    prompt: str,
    input_fn: Callable[[str], str],
    parse_yes_no: Callable[[str], bool | None],
) -> bool | None:
    print(prompt, flush=True)
    for _ in range(_MAX_REPROMPTS):
        try:
            answer = input_fn(f"{prompt}: ")
        except (EOFError, OSError):
            return None
        if (answer or "").strip().lower() in {"cancel", "abort"}:
            return None
        parsed = parse_yes_no(answer)
        if parsed is not None:
            return parsed
        print("Please answer yes or no.", flush=True)
    return None


def reset_modal_for_tests() -> None:
    _release_modal()
