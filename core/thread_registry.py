"""Central thread registry for liveness monitoring (Sprint 2 / S2.3).

Usage
-----
Register a thread at creation time::

    from core.thread_registry import get_thread_registry
    get_thread_registry().register("jarvis-overlay-qt", thread)

Re-register when the same logical thread is restarted (overlay crash-recovery)::

    get_thread_registry().update("jarvis-overlay-qt", new_thread)

Check liveness from the watchdog::

    dead = get_thread_registry().heartbeat_check()
    # dead: list[str] of thread names whose threads are no longer alive

Threads may also supply a *liveness callable* instead of a Thread object, e.g.
for threads managed by a third-party library where the Thread reference is not
accessible::

    get_thread_registry().register_fn("my-lib-thread", lambda: lib.is_running())
"""

from __future__ import annotations

import threading
import weakref
from typing import Callable

from core.logger import setup_logger

logger = setup_logger("jarvis.core.thread_registry")


class ThreadRegistry:
    """
    Tracks named daemon threads and detects unexpected deaths.

    Thread references are stored as weak references so the registry never
    prevents garbage collection of stopped threads.  Liveness callables are
    stored as strong references (they are cheap closures, not objects).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # name → weakref to threading.Thread
        self._threads: dict[str, weakref.ref[threading.Thread]] = {}
        # name → callable that returns True if the thread is alive
        self._fns: dict[str, Callable[[], bool]] = {}

    # ---------------------------------------------------------------
    # Registration
    # ---------------------------------------------------------------

    def register(self, name: str, thread: threading.Thread) -> None:
        """Register a Thread object under *name*."""
        with self._lock:
            self._threads[name] = weakref.ref(thread)
            self._fns.pop(name, None)
        logger.debug("ThreadRegistry: registered '%s' tid=%s", name, thread.ident)

    def register_fn(self, name: str, fn: Callable[[], bool]) -> None:
        """Register a liveness callable under *name* (returns True when alive)."""
        with self._lock:
            self._fns[name] = fn
            self._threads.pop(name, None)
        logger.debug("ThreadRegistry: registered_fn '%s'", name)

    def update(self, name: str, thread: threading.Thread) -> None:
        """Replace a previously registered thread (use after crash-restart)."""
        with self._lock:
            self._threads[name] = weakref.ref(thread)
            self._fns.pop(name, None)
        logger.debug("ThreadRegistry: updated '%s' tid=%s", name, thread.ident)

    def deregister(self, name: str) -> None:
        """Remove a thread from monitoring (e.g. on intentional shutdown)."""
        with self._lock:
            self._threads.pop(name, None)
            self._fns.pop(name, None)

    def deregister_if_thread(self, name: str, thread: threading.Thread) -> bool:
        """Remove *name* only when it still points at *thread*."""
        with self._lock:
            ref = self._threads.get(name)
            if ref is None or ref() is not thread:
                return False
            self._threads.pop(name, None)
            self._fns.pop(name, None)
            return True

    # ---------------------------------------------------------------
    # Liveness check
    # ---------------------------------------------------------------

    def heartbeat_check(self) -> list[str]:
        """
        Check all registered threads.  Returns the names of any that are no
        longer alive.  Logs a CRITICAL message for each dead thread and pushes
        an overlay notification.
        """
        dead: list[str] = []
        with self._lock:
            snapshot_threads = dict(self._threads)
            snapshot_fns = dict(self._fns)

        for name, ref in snapshot_threads.items():
            thread = ref()  # dereference weak ref
            alive = thread is not None and thread.is_alive()
            if not alive:
                dead.append(name)

        for name, fn in snapshot_fns.items():
            try:
                alive = bool(fn())
            except Exception as exc:
                logger.warning("ThreadRegistry: liveness check for '%s' raised: %s", name, exc)
                alive = False
            if not alive:
                dead.append(name)

        for name in dead:
            logger.critical("ThreadRegistry: thread '%s' is DEAD (unexpected exit)", name)
            try:
                from ui.overlay_app import notify_overlay_error
                notify_overlay_error(f"Thread '{name}' died unexpectedly")
            except Exception:
                pass

        return dead

    def registered_names(self) -> list[str]:
        """Return all currently registered thread names."""
        with self._lock:
            return sorted(set(self._threads) | set(self._fns))

    def snapshot(self) -> dict[str, bool]:
        """Return {name: is_alive} for all registered threads."""
        result: dict[str, bool] = {}
        with self._lock:
            snapshot_threads = dict(self._threads)
            snapshot_fns = dict(self._fns)
        for name, ref in snapshot_threads.items():
            t = ref()
            result[name] = t is not None and t.is_alive()
        for name, fn in snapshot_fns.items():
            try:
                result[name] = bool(fn())
            except Exception:
                result[name] = False
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: ThreadRegistry | None = None
_registry_lock = threading.Lock()


def get_thread_registry() -> ThreadRegistry:
    """Return the process-wide ThreadRegistry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ThreadRegistry()
    return _registry
