"""Launch Atlas — one-click desktop entry (Phase 143, refreshed Phase 155).

No terminal knowledge required.

Install modes
-------------
* Windows beta (installer): double-click the Atlas desktop/Start-menu shortcut.
  No Python is required — the installer ships a self-contained Atlas.exe.
* Source mode (developers): Python 3.10+ is required. Run:
      py -3 run_atlas.py        (Windows)
      python3 run_atlas.py      (macOS / Linux)

Atlas opens your browser automatically and shows a clean loading screen while
the local server starts. If startup fails, Atlas opens the Support page with a
plain-language explanation, "Copy diagnostics", and "Open support bundle" — it
never shows a raw traceback to a normal user.
"""

from __future__ import annotations

import argparse
import sys


def _frozen_launch() -> bool:
    return bool(getattr(sys, "frozen", False))


def _launcher_log(message: str) -> None:
    try:
        from jarvis_desktop.install_support import append_launcher_log

        append_launcher_log(message)
    except Exception:
        pass


def _install_source_excepthook() -> None:
    """175D — log fatals locally and open startup-error instead of a console traceback."""
    import traceback

    def _hook(exc_type, exc, tb) -> None:
        _launcher_log("FATAL: " + "".join(traceback.format_exception(exc_type, exc, tb))[:8000])
        try:
            from jarvis_desktop import server

            server.run(
                host="127.0.0.1",
                port=0,
                open_browser=True,
                start_path="/startup-error.html",
            )
        except Exception as fallback_exc:
            _launcher_log(f"startup-error fallback failed: {type(fallback_exc).__name__}: {fallback_exc}")

    sys.excepthook = _hook


def _safe_console_print(message: str) -> None:
    """Avoid Unicode console crashes on CP1252 redirected terminals."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="replace").decode("ascii"))


def _run_self_test_cli() -> int:
    """Run the post-install self-test, write a report file, and return 0/1."""
    import json
    import os

    from jarvis_desktop.install_support import (
        append_launcher_log,
        data_dir,
        installer_self_test,
    )

    result = installer_self_test()
    try:
        os.makedirs(data_dir(), exist_ok=True)
        report = os.path.join(data_dir(), "self_test.json")
        with open(report, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    except OSError:
        report = "(could not write report)"
    append_launcher_log(f"self-test cli ready={result.get('ready')} report={report}")
    if not _frozen_launch():
        print(f"  Atlas self-test: {'READY' if result.get('ready') else 'ISSUES FOUND'}")
        for item in result.get("checks") or []:
            mark = "[ok]" if item.get("ok") else ("[--]" if item.get("optional") else "[X]")
            print(f"    {mark} {item.get('label')}: {item.get('detail')}")
        print(f"  Report: {report}")
    return 0 if result.get("ready") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlas Repository Intelligence — launcher")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--fastapi", action="store_true", help="Use FastAPI/uvicorn if installed.")
    ap.add_argument("--support", action="store_true", help="Open Support & diagnostics page.")
    ap.add_argument("--self-test", action="store_true", help="Run the installer self-test and exit.")
    args = ap.parse_args()

    if getattr(args, "self_test", False):
        return _run_self_test_cli()

    from jarvis_desktop.install_support import append_launcher_log, installer_self_test, startup_checks
    from jarvis_desktop import server

    if not _frozen_launch():
        _install_source_excepthook()

    checks = startup_checks()
    append_launcher_log(f"startup ready={checks.get('ready')}")

    # Phase 157 — post-install self-test (binary, assets, shortcuts, browser).
    # Logged locally only; warnings never block launch.
    try:
        self_test = installer_self_test()
        append_launcher_log(
            "selftest ready={ready} warnings={warns} critical={crit}".format(
                ready=self_test.get("ready"),
                warns=",".join(self_test.get("warnings") or []) or "none",
                crit=",".join(self_test.get("critical_failures") or []) or "none",
            )
        )
    except Exception as exc:  # never block launch on a self-test error
        append_launcher_log(f"selftest error: {type(exc).__name__}: {exc}")

    if not checks.get("ready"):
        if _frozen_launch():
            _launcher_log("startup not ready: " + str(checks.get("data_dir")))
            for item in checks.get("checks") or []:
                if item.get("ok") or item.get("id") == "optional":
                    continue
                _launcher_log(f"check fail {item.get('label')}: {item.get('detail')}")
        else:
            _safe_console_print("\n  Atlas — startup check found issues:\n")
            for item in checks.get("checks") or []:
                if item.get("ok") or item.get("id") == "optional":
                    continue
                _safe_console_print(f"    [X] {item.get('label')}: {item.get('detail')}")
                if item.get("hint"):
                    _safe_console_print(f"      -> {item.get('hint')}")
            _safe_console_print("\n  Opening Atlas Support so you can fix or export diagnostics.\n")
        args.support = True

    if not checks.get("ready"):
        open_path = "/startup-error.html"
    elif args.support:
        open_path = "/support.html"
    else:
        open_path = "/"
    if args.fastapi:
        try:
            import uvicorn  # type: ignore

            if not args.no_browser:
                import threading
                import webbrowser

                def _open() -> None:
                    import time
                    time.sleep(0.8)
                    webbrowser.open(f"http://{args.host}:{args.port}{open_path}")

                threading.Thread(target=_open, daemon=True).start()
            uvicorn.run(server.create_fastapi_app(), host=args.host, port=args.port)
            return 0
        except Exception as exc:
            if not _frozen_launch():
                print(f"  FastAPI unavailable ({exc}); using built-in server.")
            else:
                _launcher_log(f"FastAPI unavailable ({exc}); using built-in server.")

    try:
        server.run(
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
            start_path=open_path,
        )
    except OSError as exc:
        append_launcher_log(f"launch bind failed: {type(exc).__name__}: {exc}")
        if not _frozen_launch():
            _safe_console_print("\n  Atlas could not bind the requested port. Opening startup-error page.\n")
        server.run(
            host=args.host,
            port=0,
            open_browser=not args.no_browser,
            start_path="/startup-error.html",
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
