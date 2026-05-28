"""Non-blocking interactive operator console (stdin thread)."""

from __future__ import annotations

import sys
import threading
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.logger import setup_logger

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.ui.operator_console")

PROMPT = "JARVIS> "
STARTUP_BANNER = "[INFO] Interactive console enabled. Type commands and press Enter."
UNAVAILABLE_WARNING = "Interactive console unavailable in background/tray mode."

# Meta commands (not routed through router).
_META_QUIT = frozenset({"quit", "exit", "q"})
_META_RESTART_OVERLAY = frozenset(
    {"restart overlay", "restart the overlay", "reset overlay"}
)

# Aliases → router phrase (same intents as voice/console).
_COMMAND_ALIASES: dict[str, str] = {
    "force shell tts test": "force shell tts test",
    "test normal speech path": "test normal speech path",
    "tool mode status": "tool mode status",
    "phase 45 status": "phase 45 status",
    "phase 46 status": "phase 46 status",
    "inspect project": "inspect project",
    "inspect website project": "inspect website project",
    "summarize current project": "summarize current project",
    "find failing tests": "find failing tests",
    "explain latest error": "explain latest error",
    "investigate trading mismatch": "investigate trading mismatch",
    "compare live vs backtest": "compare live vs backtest",
    "inspect latest live report": "inspect latest live report",
    "inspect latest backtest report": "inspect latest backtest report",
    "find recent code changes": "find recent code changes",
    "propose investigation plan": "propose investigation plan",
    "run safe diagnostics": "run safe diagnostics",
    "generate findings report": "generate findings report",
    "build investigation graph": "build investigation graph",
    "show investigation graph": "show investigation graph",
    "trace algorithm behavior": "trace algorithm behavior",
    "diff live and backtest logic": "diff live and backtest logic",
    "hunt algorithm bugs": "hunt algorithm bugs",
    "propose algorithm patch": "propose algorithm patch",
    "plan verification run": "plan verification run",
    "replay latest signal": "replay latest signal",
    "verify top hypothesis": "verify top hypothesis",
    "verify all hypotheses": "verify all hypotheses",
    "show replay timeline": "show replay timeline",
    "investigation confidence report": "investigation confidence report",
    "simulate patch for top hypothesis": "simulate patch for top hypothesis",
    "run patch simulation": "run patch simulation",
    "compare replay before after": "compare replay before after",
    "estimate patch impact": "estimate patch impact",
    "generate patch simulation report": "generate patch simulation report",
    "run historical validation sweep": "run historical validation sweep",
    "show validation sweep": "show validation sweep",
    "export validation sweep": "export validation sweep",
    "compare strategy metrics before after": "compare strategy metrics before after",
    "show worst divergence symbols": "show worst divergence symbols",
    "estimate production risk": "estimate production risk",
    "recommend production action": "recommend production action",
    "show investigation summary": "show investigation summary",
    "audit price integrity": "audit price integrity",
    "compare candle sources": "compare candle sources",
    "trace price source": "trace price source",
    "find close price mismatches": "find close price mismatches",
    "inspect data cache drift": "inspect data cache drift",
    "check timestamp alignment": "check timestamp alignment",
    "check adjusted price usage": "check adjusted price usage",
    "check duplicate bars": "check duplicate bars",
    "generate price integrity report": "generate price integrity report",
    "audit execution path": "audit execution path",
    "explain zero execution attempts": "explain zero execution attempts",
    "trace signal to order": "trace signal to order",
    "show execution blockers": "show execution blockers",
    "rank execution block reasons": "rank execution block reasons",
    "inspect execution adapter": "inspect execution adapter",
    "compare signal count to order attempts": "compare signal count to order attempts",
    "generate execution investigation report": "generate execution investigation report",
    "trace signal to execution": "trace signal to execution",
    "trace blocked signal": "trace blocked signal",
    "explain top execution blocker": "explain top execution blocker",
    "reconstruct execution flow": "reconstruct execution flow",
    "show signal lifecycle timeline": "show signal lifecycle timeline",
    "rank dead signal causes": "rank dead signal causes",
    "simulate unblock scenario": "simulate unblock scenario",
    "propose execution fix": "propose execution fix",
    "generate execution flow report": "generate execution flow report",
    "simulate execution cleanup patch": "simulate execution cleanup patch",
    "compare risk before after cleanup": "compare risk before after cleanup",
    "show stale open positions": "show stale open positions",
    "propose execution cleanup patch": "propose execution cleanup patch",
    "generate execution cleanup report": "generate execution cleanup report",
    "show approved patch": "show approved patch",
    "validate patch safety": "validate patch safety",
    "validate patch safe": "validate patch safety",
    "apply approved patch": "apply approved patch",
    "apply approved patch confirm": "apply approved patch confirm",
    "rollback last patch": "rollback last patch",
    "rollback last patch confirm": "rollback last patch confirm",
    "show patch history": "show patch history",
    "validate applied patch": "validate applied patch",
    "replay after patch": "replay after patch",
    "replay validation": "replay after patch",
    "compare pre post patch": "compare pre post patch",
    "run patch workflow": "run patch workflow",
    "run patch workflow confirm": "run patch workflow confirm",
    "show patch workflow status": "show patch workflow status",
    "show runtime health": "show runtime health",
    "show healing actions": "show healing actions",
    "show stuck workers": "show stuck workers",
    "recover overlay confirm": "recover overlay confirm",
    "recover voice system confirm": "recover voice system confirm",
    "restart dashboard confirm": "restart dashboard confirm",
    "validate runtime integrity": "validate runtime integrity",
    "summarize my screen": "summarize current screen",
    "summarize trading health": "summarize trading health",
    "what was i doing": "resume last task",
    "resume last task": "resume last task",
    "show operational suggestions": "show operational suggestions",
    "show current state": "show current state",
    "phase 49 status": "phase 49 status",
    "phase 50 status": "phase 50 status",
    "what windows are open": "what windows are open",
    "show screen system status": "show screen system status",
    "show trading operations dashboard": "show trading operations dashboard",
    "show running tasks": "show running tasks",
    "show completed tasks": "show completed tasks",
    "show failed tasks": "show failed tasks",
    "rerun last task": "rerun last task",
    "show recent results": "show recent results",
    "show notifications": "show notifications",
    "clear notifications": "clear notifications",
    "explain last result": "explain last result",
    "show focused window": "show focused window",
    "switch to browser": "switch to browser",
    "switch to cursor": "switch to cursor",
    "switch to dashboard": "switch to dashboard",
    "focus terminal": "focus terminal",
    "show memory state": "show memory state",
    "continue trading investigation": "continue trading investigation",
    "open latest report": "open last report",
    "show patch simulation": "show patch simulation",
    "approve patch apply": "approve patch apply",
    "reject patch apply": "reject patch apply",
    "show audio status": "show audio status",
    "show windows audio routing": "show windows audio routing",
    "cycle windows playback target": "cycle windows playback target",
    "stop speech hard": "stop speech hard",
    "voice smoke test": "voice smoke test",
    "show launcher status": "show launcher status",
    "foundation health check": "foundation health check",
    "open dashboard": "open dashboard",
    "what am i doing": "what am i doing",
    "stop speaking": "stop speaking",
    "show runtime threads": "show runtime threads",
    "test subprocess speech": "test subprocess speech",
    "audio route prove": "audio route prove",
    "help": "help",
}

_operator_console: "OperatorConsole | None" = None


def get_operator_console() -> "OperatorConsole | None":
    return _operator_console


def should_start_operator_console(*, blocking_text_mode: bool = False) -> bool:
    if blocking_text_mode:
        return False
    if Path(sys.executable).name.lower() == "pythonw.exe":
        return False
    stdin = getattr(sys, "stdin", None)
    try:
        return bool(stdin is not None and stdin.isatty())
    except (OSError, ValueError):
        return False


class OperatorConsole:
    """Background stdin reader; routes phrases through voice/router pipeline."""

    def __init__(
        self,
        app: "JarvisApp",
        *,
        tray_app: Any | None = None,
        background_mode: bool = False,
    ) -> None:
        self._app = app
        self._tray_app = tray_app
        self._background_mode = background_mode
        self._thread: threading.Thread | None = None
        self._dispatch_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._queue_cond = threading.Condition(self._queue_lock)
        self._command_queue: deque[str] = deque()
        self._queue_worker: threading.Thread | None = None
        self._queue_processing = False
        self._started = False

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        global _operator_console
        if self._started:
            return False
        if self._background_mode or not should_start_operator_console():
            print(UNAVAILABLE_WARNING, flush=True)
            return False
        self._started = True
        _operator_console = self
        print(STARTUP_BANNER, flush=True)
        self._thread = threading.Thread(
            target=self._read_loop,
            name="jarvis-console",
            daemon=True,
        )
        self._thread.start()
        logger.info("Operator console thread started")
        return True

    def stop(self) -> None:
        global _operator_console
        self._app._running = False
        if _operator_console is self:
            _operator_console = None

    def _read_loop(self) -> None:
        while self._app._running and self._app.runtime.running:
            try:
                from ui.console_modal import is_modal_active

                if not is_modal_active():
                    sys.stdout.write(PROMPT)
                    sys.stdout.flush()
                line = sys.stdin.readline()
            except (EOFError, KeyboardInterrupt):
                print("\n[CONSOLE] stdin closed.", flush=True)
                break
            if not line:
                break
            text = line.strip()
            if not text:
                continue
            try:
                from ui.console_modal import is_modal_active, submit_modal_line

                if is_modal_active():
                    submit_modal_line(text)
                    continue
            except Exception:
                pass
            self._enqueue_command(text)

    def queue_length(self) -> int:
        with self._queue_cond:
            return len(self._command_queue)

    def _enqueue_command(self, raw: str) -> None:
        with self._queue_cond:
            self._command_queue.append(raw)
            queued_len = len(self._command_queue)
            print(f"[QUEUE] queued command: {raw}", flush=True)
            waiting = max(queued_len - (1 if self._queue_processing else 0), 0)
            if self._queue_processing:
                print(f"[QUEUE] remaining={waiting}", flush=True)
            if self._queue_processing:
                return
            self._queue_processing = True
            self._queue_worker = threading.Thread(
                target=self._process_queue,
                name="jarvis-console-queue",
                daemon=True,
            )
            self._queue_worker.start()

    def _process_queue(self) -> None:
        while self._app._running and self._app.runtime.running:
            with self._queue_cond:
                if not self._command_queue:
                    self._queue_processing = False
                    self._queue_cond.notify_all()
                    return
                raw = self._command_queue.popleft()
                remaining = len(self._command_queue)
            print(f"[QUEUE] executing command: {raw}", flush=True)
            print(f"[QUEUE] remaining={remaining}", flush=True)
            done = threading.Event()
            try:
                with self._dispatch_lock:
                    self._handle_line(raw, done_event=done)
                if not done.wait(timeout=600.0):
                    print(f"[QUEUE] WARNING command timed out: {raw}", flush=True)
            except Exception as exc:
                logger.exception("operator console queued command failed")
                message = f"Console command failed: {exc}"
                print(f"[CONSOLE] ERROR {message}", flush=True)
                try:
                    from ui.overlay_app import notify_overlay_error

                    notify_overlay_error(message[:200])
                except Exception:
                    pass
            finally:
                done.set()
                print(f"[QUEUE] completed command: {raw}", flush=True)
                with self._queue_cond:
                    print(f"[QUEUE] remaining={len(self._command_queue)}", flush=True)

    def _dispatch_line(self, raw: str) -> None:
        try:
            from ui.console_modal import is_modal_active

            if is_modal_active():
                return
        except Exception:
            pass
        self._enqueue_command(raw)

    def _resolve_phrase(self, raw: str) -> str:
        from brain.patch_command_phrases import normalize_patch_command

        canonical = normalize_patch_command(raw.strip()).lower()
        if not canonical:
            canonical = raw.strip().lower()
        return _COMMAND_ALIASES.get(canonical, canonical)

    def _handle_line(self, raw: str, *, done_event: threading.Event | None = None) -> None:
        lower = raw.strip().lower()
        print("[CONSOLE] command received", flush=True)
        try:
            if lower in _META_QUIT:
                print("[CONSOLE] exit requested.", flush=True)
                self._shutdown()
                return
            if lower in _META_RESTART_OVERLAY:
                self._restart_overlay()
                return

            phrase = self._resolve_phrase(raw)
            if lower == "help" or phrase.lower() == "help":
                self._print_help()
                return

            from voice.voice_loop import process_console_command

            process_console_command(
                self._app,
                phrase,
                tray_app=self._tray_app,
            )
        finally:
            if done_event is not None:
                done_event.set()

    def _restart_overlay(self) -> None:
        try:
            from ui.overlay_app import get_overlay_controller

            ctrl = get_overlay_controller()
            ctrl._state.reset()
            ctrl.on_ready(quiet=True)
            print("[CONSOLE] overlay restarted (state reset).", flush=True)
        except Exception as exc:
            print(f"[CONSOLE] overlay restart failed: {exc}", flush=True)

    def _shutdown(self) -> None:
        self._app._running = False
        self._app.runtime.stop()
        if self._tray_app is not None:
            try:
                self._tray_app.stop()
            except Exception as exc:
                logger.debug("tray stop from console: %s", exc)

    def _print_help(self) -> None:
        lines = [
            "Operator console commands:",
            "  force shell tts test",
            "  test normal speech path",
            "  tool mode status",
            "  phase 45 status",
            "  phase 46 status",
            "  inspect project",
            "  inspect website project",
            "  find failing tests",
            "  compare live vs backtest",
            "  trace algorithm behavior",
            "  hunt algorithm bugs",
            "  replay latest signal",
            "  verify top hypothesis",
            "  show replay timeline",
            "  simulate patch for top hypothesis",
            "  run patch simulation",
            "  compare replay before after",
            "  estimate patch impact",
            "  run historical validation sweep",
            "  show validation sweep",
            "  show worst divergence symbols",
            "  recommend production action",
            "  audit price integrity",
            "  find close price mismatches",
            "  generate price integrity report",
            "  audit execution path",
            "  explain zero execution attempts",
            "  show execution blockers",
            "  generate execution investigation report",
            "  reconstruct execution flow",
            "  trace blocked signal AAPL",
            "  explain top execution blocker",
            "  generate execution flow report",
            "  simulate execution cleanup patch",
            "  show stale open positions",
            "  compare risk before after cleanup",
            "  propose execution cleanup patch",
            "  generate execution cleanup report",
            "  validate patch safety",
            "  show approved patch",
            "  apply approved patch confirm",
            "  run patch workflow confirm",
            "  show patch workflow status",
            "  replay after patch",
            "  compare pre post patch",
            "  rollback last patch confirm",
            "  generate findings report",
            "  show audio status",
            "  test direct speech",
            "  verify direct speech backend",
            "  force verified direct speech confirm",
            "  test normal speech path",
            "  show windows audio routing",
            "  cycle windows playback target",
            "  stop speech hard",
            "  voice smoke test",
            "  show launcher status",
            "  foundation health check",
            "  open dashboard",
            "  what am i doing",
            "  stop speaking",
            "  show runtime threads",
            "  restart overlay",
            "  show running tasks",
            "  cancel task 3",
            "  show completed tasks",
            "  show failed tasks",
            "  show recent results",
            "  show notifications",
            "  clear notifications",
            "  explain last result",
            "  rerun last task",
            "  continue previous session",
            "  summarize unresolved issues",
            "  recommend next action",
            "  run investigation cycle",
            "  show investigation schedule",
            "  show blocker trends",
            "  show active hypotheses",
            "  explain top hypothesis",
            "  show intelligence timeline",
            "  summarize autonomous findings",
            "  explain current trading risk",
            "  summarize root causes",
            "  verify root causes",
            "  show verification plans",
            "  show confidence evolution",
            "  show contradictory evidence",
            "  suggest experiments",
            "  show root cause graph",
            "  explain dominant root cause",
            "  explain why trades are blocked",
            "  reopen task result 7",
            "  explain notification 2",
            "  summarize trading health",
            "  quit / exit",
        ]
        print("\n".join(lines), flush=True)


def start_operator_console(
    app: "JarvisApp",
    *,
    tray_app: Any | None = None,
    background_mode: bool = False,
) -> OperatorConsole | None:
    console = OperatorConsole(app, tray_app=tray_app, background_mode=background_mode)
    if console.start():
        return console
    return None
