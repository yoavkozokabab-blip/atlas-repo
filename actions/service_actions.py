"""Autostart, health, and watchdog actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from services.autostart import (
    AutostartError,
    disable_autostart,
    enable_autostart,
    get_autostart_status,
)
from services.health import run_jarvis_health_check
from services.watchdog import WatchdogService


class EnableAutostartAction(BaseAction):
    intent = Intent.ENABLE_AUTOSTART.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            status = enable_autostart()
            summary = (
                "Windows Startup autostart enabled.\n"
                f"Shortcut: {status.get('shortcut_path')}\n"
                f"Target script: {status.get('tray_script')}"
            )
            return result_success(
                Intent.ENABLE_AUTOSTART,
                summary,
                data=status,
            )
        except AutostartError as exc:
            return result_failed(Intent.ENABLE_AUTOSTART, str(exc), error=str(exc))


class DisableAutostartAction(BaseAction):
    intent = Intent.DISABLE_AUTOSTART.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            status = disable_autostart()
            return result_success(
                Intent.DISABLE_AUTOSTART,
                "Windows Startup autostart disabled.",
                data=status,
            )
        except AutostartError as exc:
            return result_failed(Intent.DISABLE_AUTOSTART, str(exc), error=str(exc))


class ShowAutostartStatusAction(BaseAction):
    intent = Intent.SHOW_AUTOSTART_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        status = get_autostart_status()
        enabled = status.get("enabled")
        lines = [
            f"Autostart enabled: {'yes' if enabled else 'no'}",
            f"Method: {status.get('method')}",
            f"Shortcut: {status.get('shortcut_path')}",
            f"Tray script: {status.get('tray_script')}",
            f"Script exists: {status.get('tray_script_exists')}",
        ]
        if enabled:
            lines.append(f"Target valid: {status.get('target_valid')}")
            lines.append(f"Arguments valid: {status.get('arguments_valid')}")
        return result_success(
            Intent.SHOW_AUTOSTART_STATUS,
            "\n".join(lines),
            data=status,
        )


class RunJarvisHealthCheckAction(BaseAction):
    intent = Intent.RUN_JARVIS_HEALTH_CHECK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        report = run_jarvis_health_check()
        if report.overall == "ok":
            st = ActionStatus.SUCCESS
        elif report.overall == "critical":
            st = ActionStatus.FAILED
        else:
            st = ActionStatus.CLARIFICATION_NEEDED

        return CommandResult(
            intent=Intent.RUN_JARVIS_HEALTH_CHECK,
            status=st,
            summary=report.summary,
            data=report.to_dict(),
            next_suggestions=[
                "Run: show watchdog status",
                "Run: run diagnostics",
            ],
        )


class ShowWatchdogStatusAction(BaseAction):
    intent = Intent.SHOW_WATCHDOG_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        status = WatchdogService.load_status()
        overall = status.get("overall", "unknown")
        lines = [
            f"Watchdog overall: {overall}",
            f"Updated: {status.get('updated_at', 'n/a')}",
            f"Interval: {status.get('interval_seconds', 'n/a')}s",
            f"Repairs performed: {status.get('repairs_performed', False)}",
            f"Recovery enabled: {status.get('recovery_enabled', 'n/a')}",
        ]
        recoveries = status.get("recoveries") or []
        if recoveries:
            lines.append("Recent recoveries:")
            for item in recoveries[:5]:
                lines.append(
                    "  - "
                    f"{item.get('component')}:{item.get('action')} "
                    f"ok={item.get('ok')} reason={item.get('reason')}"
                )
        runtime_monitor = status.get("runtime_monitor") or {}
        if runtime_monitor:
            lines.append(
                f"Runtime monitor: {runtime_monitor.get('overall', 'unknown')} "
                f"(threads={runtime_monitor.get('threads', {}).get('jarvis_total', 'n/a')}, "
                f"rss={runtime_monitor.get('memory', {}).get('rss_mb', 'n/a')} MB)"
            )
        issues = status.get("issues") or []
        if issues:
            lines.append("Issues:")
            for issue in issues[:8]:
                lines.append(f"  - {issue}")
        else:
            lines.append("No open issues in last watchdog pass.")
        if status.get("summary"):
            lines.append("")
            lines.append(str(status["summary"])[:500])
        return result_success(
            Intent.SHOW_WATCHDOG_STATUS,
            "\n".join(lines),
            data=status,
        )
