"""System status reporting."""

from __future__ import annotations

import socket

import psutil

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _cpu_ram_lines() -> list[str]:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    return [
        f"CPU usage: {cpu}%",
        f"RAM: {mem.percent}% used ({_format_bytes(mem.used)} / {_format_bytes(mem.total)})",
    ]


def _disk_lines() -> list[str]:
    lines: list[str] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        lines.append(
            f"Disk {part.device}: {usage.percent}% used "
            f"({_format_bytes(usage.used)} / {_format_bytes(usage.total)})"
        )
    return lines


def _network_lines() -> list[str]:
    lines: list[str] = []
    try:
        host = socket.gethostname()
        addrs: list[str] = []
        for _name, addr_list in psutil.net_if_addrs().items():
            for addr in addr_list:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    addrs.append(addr.address)
        lines.append(f"Hostname: {host}")
        if addrs:
            lines.append(f"IPv4: {', '.join(sorted(set(addrs))[:5])}")
    except Exception:
        lines.append("Network: status unavailable")
    return lines


class ShowSystemStatusAction(BaseAction):
    intent = Intent.SHOW_SYSTEM_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        lines = _cpu_ram_lines() + _disk_lines() + _network_lines()
        summary = "\n".join(lines)
        return result_success(
            Intent.SHOW_SYSTEM_STATUS,
            summary,
            data={"summary": summary},
        )


class ShowDiskUsageAction(BaseAction):
    intent = Intent.SHOW_DISK_USAGE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        lines = _disk_lines()
        if not lines:
            return result_failed(Intent.SHOW_DISK_USAGE, "No disk usage data available.")
        return result_success(Intent.SHOW_DISK_USAGE, "\n".join(lines))


class ShowNetworkStatusAction(BaseAction):
    intent = Intent.SHOW_NETWORK_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return result_success(
            Intent.SHOW_NETWORK_STATUS,
            "\n".join(_network_lines()),
        )
