"""Watchdog execution context — tray-optional host for WatchdogService (Sprint 3.2)."""

from __future__ import annotations

from typing import Any

from core.runtime_state import RuntimeState, get_runtime_state


class WatchdogContext:
    """
    Supplies runtime/voice-thread/recovery hooks to WatchdogService.

    Tray mode attaches a tray app for in-process recovery; CLI/voice modes
    run headless with thread-registry heartbeat only.
    """

    def __init__(
        self,
        runtime: RuntimeState | None = None,
        *,
        tray_app: Any | None = None,
    ) -> None:
        self.runtime = runtime or get_runtime_state()
        self.tray_app = tray_app

    @property
    def voice_thread(self) -> Any | None:
        tray = self.tray_app
        if tray is not None:
            return getattr(tray, "_voice_thread", None)
        return None

    @property
    def tray_running(self) -> bool:
        return bool(getattr(self.runtime, "tray_enabled", False))

    def restart_background_services(self, *, reason: str = "watchdog") -> list[dict[str, object]]:
        tray = self.tray_app
        if tray is None:
            return []
        restart = getattr(tray, "restart_background_services", None)
        if not callable(restart):
            return []
        raw = restart(reason=reason)
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return []
