"""PyInstaller entrypoint for Atlas.exe (windowed, no console).

Runs startup checks, local server, and browser open. Logs failures locally;
never relies on a visible terminal.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _prepare_runtime() -> None:
    if _frozen():
        exe_dir = Path(sys.executable).resolve().parent
        os.chdir(exe_dir)
        if hasattr(sys, "_MEIPASS"):
            meipass = str(Path(sys._MEIPASS))
            if meipass not in sys.path:
                sys.path.insert(0, meipass)
        root = exe_dir
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))


def _log_fatal(message: str) -> None:
    try:
        from jarvis_desktop.install_support import append_launcher_log

        append_launcher_log(message[:8000])
    except Exception:
        pass


def _install_excepthook() -> None:
    def _hook(exc_type, exc, tb) -> None:
        _log_fatal("FATAL: " + "".join(traceback.format_exception(exc_type, exc, tb)))
        _open_support_fallback()

    sys.excepthook = _hook


def _open_support_fallback() -> None:
    try:
        from jarvis_desktop import server

        server.run(host="127.0.0.1", port=8777, open_browser=True, start_path="/support.html")
    except Exception as exc:
        _log_fatal(f"support fallback failed: {type(exc).__name__}: {exc}")


def main() -> int:
    _prepare_runtime()
    _install_excepthook()
    try:
        from run_atlas import main as run_main

        return int(run_main() or 0)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    except Exception:
        _log_fatal("FATAL: " + traceback.format_exc())
        _open_support_fallback()
        return 1


if __name__ == "__main__":
    sys.exit(main())
