"""Launch JARVIS Desktop — Repository Intelligence Platform (Phase 107 MVP).

Zero external dependencies: serves a local web app with Python's stdlib.
    py -3 run_jarvis_desktop.py [--port 8777] [--host 127.0.0.1] [--no-browser]

If FastAPI + uvicorn are installed, pass --fastapi to use them instead.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="JARVIS Desktop launcher")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--fastapi", action="store_true", help="Use FastAPI/uvicorn if installed.")
    args = ap.parse_args()

    from jarvis_desktop import server

    if args.fastapi:
        try:
            import uvicorn  # type: ignore
            uvicorn.run(server.create_fastapi_app(), host=args.host, port=args.port)
            return 0
        except Exception as exc:  # fall back to stdlib
            print(f"  FastAPI unavailable ({exc}); falling back to stdlib server.")

    server.run(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
