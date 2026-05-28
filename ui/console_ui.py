"""Reusable console interaction loop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from core.app import JarvisApp


def run_console_loop(app: "JarvisApp") -> None:
    """Blocking text console — same handler as tray-triggered commands."""
    tts_hint = " [bold]TTS on[/]" if app.speak_enabled else ""
    app.console.print(
        Panel(
            f"[bold cyan]JARVIS[/] — console{tts_hint}\n"
            "Type [bold]help[/] or [bold]quit[/].",
            title="local_jarvis",
        )
    )
    while app._running and app.runtime.running:
        try:
            text = app.console.input("[bold green]You>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            app.console.print("\n[yellow]Console closed.[/]")
            break

        if not text:
            continue

        lower = text.lower()
        if lower in {"quit", "exit", "q"}:
            app.console.print("[yellow]Goodbye.[/]")
            break
        if lower == "help":
            app._print_help()
            continue

        app.handle_text_command(text, input_mode="text")


def open_console_window(project_root: str) -> None:
    """Launch a new terminal with text console (Windows)."""
    import subprocess

    subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            "start",
            "cmd.exe",
            "/k",
            f"cd /d {project_root} && python main.py --text",
        ],
        shell=False,
        cwd=project_root,
    )
