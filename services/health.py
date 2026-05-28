"""Local JARVIS health checks (read-only, no repairs)."""

from __future__ import annotations

import os
import shutil
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    COMMAND_HISTORY_PATH,
    LLM_CLASSIFIER_ENABLED,
    OLLAMA_BASE_URL,
    PROJECT_ROOT,
    VISION_ENABLED,
)
from core.logger import setup_logger

logger = setup_logger("jarvis.services.health")


@dataclass
class HealthCheckItem:
    name: str
    status: str  # ok, warning, critical
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class HealthReport:
    overall: str
    checks: list[HealthCheckItem] = field(default_factory=list)
    summary: str = ""
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "summary": self.summary,
            "checked_at": self.checked_at,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "evidence": c.evidence,
                }
                for c in self.checks
            ],
        }


def _overall_status(checks: list[HealthCheckItem]) -> str:
    if any(c.status == "critical" for c in checks):
        return "critical"
    if any(c.status == "warning" for c in checks):
        return "warning"
    return "ok"


def _tesseract_available() -> bool:
    try:
        from vision.ocr import _tesseract_available

        return _tesseract_available()
    except Exception:
        return False


def _ollama_reachable() -> tuple[bool, str]:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if 200 <= resp.status < 300:
                return True, "reachable"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)
    return False, "unexpected response"


def run_jarvis_health_check(
    *,
    runtime: Any | None = None,
    voice_thread: threading.Thread | None = None,
    tray_running: bool | None = None,
) -> HealthReport:
    """
    Read-only health pass for JARVIS process and dependencies.
    Does not repair or restart anything.
    """
    checks: list[HealthCheckItem] = []
    now = datetime.now(timezone.utc).isoformat()

    if runtime is not None:
        if not getattr(runtime, "running", True):
            checks.append(
                HealthCheckItem(
                    "app_running",
                    "warning",
                    "Runtime flag running=false.",
                )
            )
        else:
            checks.append(
                HealthCheckItem("app_running", "ok", "JARVIS runtime is active.")
            )

        if getattr(runtime, "voice_enabled", False):
            alive = voice_thread is not None and voice_thread.is_alive()
            if alive:
                checks.append(
                    HealthCheckItem("voice_thread", "ok", "Voice thread is alive.")
                )
            else:
                checks.append(
                    HealthCheckItem(
                        "voice_thread",
                        "critical",
                        "Voice enabled but background voice thread is not running.",
                    )
                )
        else:
            checks.append(
                HealthCheckItem("voice_thread", "ok", "Voice mode disabled.")
            )

        if getattr(runtime, "tray_enabled", False):
            checks.append(
                HealthCheckItem("tray_state", "ok", "Tray mode enabled.")
            )
        elif tray_running:
            checks.append(
                HealthCheckItem("tray_state", "ok", "Tray session active.")
            )

        last_err = getattr(runtime, "last_error", None)
        if last_err:
            checks.append(
                HealthCheckItem(
                    "last_command_error",
                    "warning",
                    "Last command recorded an error.",
                    evidence=[str(last_err)[:200]],
                )
            )
        else:
            checks.append(
                HealthCheckItem("last_command_error", "ok", "No recent command error.")
            )
    else:
        checks.append(
            HealthCheckItem(
                "app_running",
                "info",
                "Runtime state not provided (standalone health check).",
            )
        )

    if VISION_ENABLED and not _tesseract_available():
        checks.append(
            HealthCheckItem(
                "tesseract",
                "warning",
                "VISION_ENABLED but Tesseract OCR is not available.",
                evidence=["Install Tesseract or set TESSERACT_CMD in .env"],
            )
        )
    elif VISION_ENABLED:
        checks.append(
            HealthCheckItem("tesseract", "ok", "Tesseract available for vision OCR.")
        )

    if LLM_CLASSIFIER_ENABLED:
        ok, detail = _ollama_reachable()
        if ok:
            checks.append(
                HealthCheckItem(
                    "ollama",
                    "ok",
                    f"Ollama reachable at {OLLAMA_BASE_URL}.",
                )
            )
        else:
            checks.append(
                HealthCheckItem(
                    "ollama",
                    "critical",
                    "LLM classifier enabled but Ollama is unreachable.",
                    evidence=[detail[:200]],
                )
            )
    else:
        checks.append(
            HealthCheckItem("ollama", "ok", "LLM classifier disabled.")
        )

    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        free_gb = usage.free / (1024**3)
        if free_gb < 1.0:
            checks.append(
                HealthCheckItem(
                    "disk_free",
                    "critical",
                    f"Low disk space on project volume ({free_gb:.2f} GB free).",
                )
            )
        elif free_gb < 5.0:
            checks.append(
                HealthCheckItem(
                    "disk_free",
                    "warning",
                    f"Disk space getting low ({free_gb:.2f} GB free).",
                )
            )
        else:
            checks.append(
                HealthCheckItem(
                    "disk_free",
                    "ok",
                    f"{free_gb:.1f} GB free on project volume.",
                )
            )
    except OSError as exc:
        checks.append(
            HealthCheckItem(
                "disk_free",
                "warning",
                f"Could not check disk space: {exc}",
            )
        )

    history_path = COMMAND_HISTORY_PATH
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8"):
            pass
        checks.append(
            HealthCheckItem(
                "command_history",
                "ok",
                "Command history path is writable.",
                evidence=[str(history_path)],
            )
        )
    except OSError as exc:
        checks.append(
            HealthCheckItem(
                "command_history",
                "critical",
                "Command history path is not writable.",
                evidence=[str(exc)],
            )
        )

    overall = _overall_status(checks)
    lines = [f"JARVIS health: {overall.upper()}"]
    for c in checks:
        lines.append(f"  [{c.status}] {c.name}: {c.message}")
    return HealthReport(
        overall=overall,
        checks=checks,
        summary="\n".join(lines),
        checked_at=now,
    )
