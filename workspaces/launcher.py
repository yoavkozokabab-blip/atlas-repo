"""Phase 26 — smart workspace launcher (approved apps/sites only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkspaceStep:
    phrase: str
    description: str


WORKSPACES: dict[str, list[WorkspaceStep]] = {
    "trading": [
        WorkspaceStep("open trading dashboard", "Trading dashboard (localhost)"),
        WorkspaceStep("open tradingview", "TradingView (allowlisted)"),
        WorkspaceStep("show dashboard health", "Dashboard health check"),
        WorkspaceStep("show task status", "Supervised task status"),
    ],
    "study": [
        WorkspaceStep("open chatgpt", "ChatGPT (allowlisted)"),
        WorkspaceStep("open youtube", "YouTube"),
        WorkspaceStep("open google", "Google"),
    ],
    "dev": [
        WorkspaceStep("open cursor", "Cursor IDE"),
        WorkspaceStep("open project folder", "Project folder"),
        WorkspaceStep("open terminal", "Terminal"),
        WorkspaceStep("run diagnostics", "JARVIS diagnostics"),
    ],
}


def workspace_plan(name: str) -> tuple[str, list[str]]:
    steps = WORKSPACES.get(name, [])
    if not steps:
        return f"Unknown workspace '{name}'.", []
    lines = [f"Workspace: {name}", "Run these commands in order (each via router):"]
    phrases = []
    for i, s in enumerate(steps, 1):
        lines.append(f"  {i}. {s.phrase} — {s.description}")
        phrases.append(s.phrase)
    lines.append("")
    lines.append("_JARVIS does not auto-run workspace steps; say each phrase or use the tray menu._")
    return "\n".join(lines), phrases
