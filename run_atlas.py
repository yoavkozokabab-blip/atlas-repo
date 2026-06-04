"""Launch Atlas — one-click desktop entry (Phase 143).

No terminal knowledge required: double-click Launch Atlas.bat or run:
    py -3 run_atlas.py
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlas Repository Intelligence — launcher")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--fastapi", action="store_true", help="Use FastAPI/uvicorn if installed.")
    ap.add_argument("--support", action="store_true", help="Open Support & diagnostics page.")
    args = ap.parse_args()

    from jarvis_desktop.install_support import append_launcher_log, startup_checks
    from jarvis_desktop import server

    checks = startup_checks()
    append_launcher_log(f"startup ready={checks.get('ready')}")

    if not checks.get("ready"):
        if _frozen_launch():
            _launcher_log("startup not ready: " + str(checks.get("data_dir")))
            for item in checks.get("checks") or []:
                if item.get("ok") or item.get("id") == "optional":
                    continue
                _launcher_log(f"check fail {item.get('label')}: {item.get('detail')}")
        else:
            print("\n  Atlas — startup check found issues:\n")
            for item in checks.get("checks") or []:
                if item.get("ok") or item.get("id") == "optional":
                    continue
                print(f"    ✗ {item.get('label')}: {item.get('detail')}")
                if item.get("hint"):
                    print(f"      → {item.get('hint')}")
            print("\n  Opening Atlas Support so you can fix or export diagnostics.\n")
        args.support = True

    open_path = "/support.html" if args.support else "/"
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

    server.run(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        start_path=open_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
