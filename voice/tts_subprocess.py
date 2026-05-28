"""Subprocess pyttsx3 TTS — same invocation as the known-good shell command."""

from __future__ import annotations

import subprocess
import sys
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from config import PROJECT_ROOT, TTS_TIMEOUT_SECONDS
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts.subprocess")

SUBPROCESS_BACKEND = "subprocess_pyttsx3"
SHELL_SUBPROCESS_BACKEND = "shell_subprocess_pyttsx3"

# Exact working shell one-liner (must not be altered for force shell test).
SHELL_EXACT_SAY_PHRASE = "Jarvis shell audio test from local jarvis"
SHELL_EXACT_CODE = (
    "import pyttsx3; e=pyttsx3.init(); "
    f"e.say({SHELL_EXACT_SAY_PHRASE!r}); e.runAndWait()"
)


@dataclass(frozen=True)
class SubprocessTtsResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def build_pyttsx3_subprocess_code(text: str, *, routed: bool = True) -> str:
    """Python -c body; routed mode plays via sounddevice on Windows default/session device."""
    if routed:
        from voice.windows_audio_routing import build_routed_pyttsx3_subprocess_code

        return build_routed_pyttsx3_subprocess_code(text)
    return f"import pyttsx3; e=pyttsx3.init(); e.say({text!r}); e.runAndWait()"


def build_pyttsx3_subprocess_argv(text: str) -> list[str]:
    """Argv for: py -3 -c '<code>' (matches user shell recipe)."""
    return ["py", "-3", "-c", build_pyttsx3_subprocess_code(text)]


def build_shell_exact_argv() -> list[str]:
    """Argv for the exact known-good shell command."""
    return ["py", "-3", "-c", SHELL_EXACT_CODE]


def terminate_process_tree(proc: object) -> None:
    """Terminate a timed-out TTS child and any python.exe child from py.exe."""
    pid = getattr(proc, "pid", None)
    if os.name == "nt" and pid:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
            return
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


def run_subprocess_tts_argv(
    argv: list[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    on_playback_start: Callable[[], None] | None = None,
    label: str = "TTS_SUBPROCESS",
) -> SubprocessTtsResult:
    from voice.audio_verified import may_show_speaking_overlay
    from voice.playback_guard import should_play_audio

    try:
        from core.test_runtime import allow_audio_playback, is_test_mode

        if is_test_mode() and not allow_audio_playback():
            return SubprocessTtsResult(exit_code=0, stdout="", stderr="skipped_test_guard")
    except Exception:
        pass

    if not should_play_audio():
        return SubprocessTtsResult(exit_code=0, stdout="", stderr="skipped_test_guard")

    workdir = cwd or PROJECT_ROOT
    from voice.tts_watchdog import get_subprocess_timeout_seconds

    hard_cap = get_subprocess_timeout_seconds()
    if timeout_seconds is not None:
        timeout = min(float(timeout_seconds), hard_cap)
    else:
        timeout = min(float(TTS_TIMEOUT_SECONDS), hard_cap)
    from voice.windows_audio_routing import log_tts_route_before_subprocess, subprocess_env_with_audio_route

    route = log_tts_route_before_subprocess(label=label)
    env = subprocess_env_with_audio_route()
    print(f"[{label}] start", flush=True)
    logger.info(
        "subprocess TTS start cwd=%s argv0=%s device=%s",
        workdir,
        argv[0] if argv else "",
        route.device_label,
    )

    proc = subprocess.Popen(
        argv,
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    from voice.tts_watchdog import clear_subprocess, register_subprocess

    register_subprocess(proc)
    if on_playback_start is not None and may_show_speaking_overlay():
        on_playback_start()
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=max(0.5, timeout))
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_tree(proc)
        stdout, stderr = "", ""
        stderr = f"TTS subprocess timeout after {timeout:.1f}s"
    finally:
        clear_subprocess()

    exit_code = int(proc.returncode or 0)
    out = stdout or ""
    err = stderr or ""
    print(f"[{label}] exit_code {exit_code}", flush=True)
    if out.strip():
        print(f"[{label}] stdout {out.strip()[:500]}", flush=True)
    if err.strip():
        print(f"[{label}] stderr {err.strip()[:500]}", flush=True)

    result = SubprocessTtsResult(
        exit_code=exit_code,
        stdout=out,
        stderr=err,
        timed_out=timed_out,
    )
    try:
        from voice.audio_status import record_subprocess_tts_result

        record_subprocess_tts_result(result)
    except Exception:
        pass
    return result


def run_shell_exact_pyttsx3(
    *,
    timeout_seconds: float | None = None,
    on_playback_start: Callable[[], None] | None = None,
) -> SubprocessTtsResult:
    """Run EXACTLY: py -3 -c \"import pyttsx3; e=pyttsx3.init(); e.say('...'); e.runAndWait()\" """
    return run_subprocess_tts_argv(
        build_shell_exact_argv(),
        timeout_seconds=timeout_seconds,
        on_playback_start=on_playback_start,
        label="TTS_SUBPROCESS",
    )


def speak_subprocess_pyttsx3(
    text: str,
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    on_playback_start: Callable[[], None] | None = None,
) -> SubprocessTtsResult:
    """
    Run pyttsx3 in a child process (fresh session), equivalent to:
    cd local_jarvis && py -3 -c "import pyttsx3; ..."
    """
    argv = build_pyttsx3_subprocess_argv(text)
    return run_subprocess_tts_argv(
        argv,
        timeout_seconds=timeout_seconds,
        cwd=cwd,
        on_playback_start=on_playback_start,
        label="TTS_SUBPROCESS",
    )


def subprocess_python_display() -> str:
    return f"py -3 (cwd={PROJECT_ROOT})"
