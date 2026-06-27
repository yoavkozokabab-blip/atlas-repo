"""Packaged Atlas Desktop entry point.

This wrapper is intentionally small: it delegates normal behavior to
``run_atlas.main`` and provides a last-resort support-page fallback for packaged
startup failures.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
import sys
import time
import traceback
import webbrowser


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


def _bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent


def _support_html_path() -> Path | None:
    candidates = [
        _bundle_root() / "jarvis_desktop" / "static" / "support.html",
        Path(__file__).resolve().parent / "jarvis_desktop" / "static" / "support.html",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _diagnostics_dir() -> Path:
    try:
        from jarvis_desktop.data_paths import desktop_data_dir

        path = Path(desktop_data_dir())
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or str(Path.home())
        path = Path(base) / "Atlas" / "desktop_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_failure_diagnostics(exc: BaseException) -> Path:
    diag_dir = _diagnostics_dir()
    payload = {
        "ok": False,
        "event": "packaged_startup_failure",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "traceback": traceback.format_exc(),
    }
    json_path = diag_dir / "packaged_startup_failure.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (diag_dir / "launcher.log").open("a", encoding="utf-8") as fh:
        fh.write(
            f"{payload['generated_at']} packaged_startup_failure "
            f"{payload['exception_type']}: {payload['exception']}\n"
        )
    return json_path


def _write_fallback_page(exc: BaseException, diagnostics_path: Path) -> Path:
    support_path = _support_html_path()
    support_link = support_path.as_uri() if support_path else ""
    page = diagnostics_path.with_name("startup_failure_support.html")
    detail = html.escape(f"{type(exc).__name__}: {exc}")
    diagnostics = html.escape(str(diagnostics_path))
    support_markup = (
        f'<p><a class="button" href="{support_link}">Open Atlas support.html</a></p>'
        if support_link
        else ""
    )
    page.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atlas startup support</title>
  <style>
    body {{ margin: 0; min-height: 100vh; background: #05070c; color: #f4f7fb; font-family: Arial, sans-serif; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 56px 24px; }}
    h1 {{ font-size: 32px; margin: 0 0 12px; letter-spacing: 0; }}
    p {{ color: #b8c0cc; line-height: 1.55; }}
    code {{ color: #e8f2ff; background: #111827; padding: 3px 6px; border-radius: 4px; }}
    .panel {{ border: 1px solid #243044; background: #0b1020; padding: 18px; border-radius: 8px; }}
    .button {{ color: #061018; background: #79e4ff; padding: 10px 14px; border-radius: 6px; text-decoration: none; font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <h1>Atlas could not finish starting</h1>
    <p>Atlas saved startup diagnostics. No Python traceback is required to use this support page.</p>
    <div class="panel">
      <p><b>Failure:</b> <code>{detail}</code></p>
      <p><b>Diagnostics:</b> <code>{diagnostics}</code></p>
    </div>
    {support_markup}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return page


def _open_failure_support(exc: BaseException) -> None:
    try:
        diagnostics_path = _write_failure_diagnostics(exc)
        fallback_page = _write_fallback_page(exc, diagnostics_path)
        webbrowser.open(fallback_page.as_uri())
    except Exception:
        pass


def main() -> int:
    _prepare_runtime()
    try:
        from run_atlas import main as run_main

        return int(run_main() or 0)
    except Exception as exc:
        _open_failure_support(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
