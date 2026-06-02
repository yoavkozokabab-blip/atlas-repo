"""Local desktop server for JARVIS Desktop.

Default: a zero-dependency ``http.server`` app (always runs on Windows). The HTTP
routing is a thin wrapper over :func:`dispatch`, a pure function that tests call
directly (no sockets, no web framework). An optional FastAPI app is provided for
those who install fastapi/uvicorn, but it is **not** required.
"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any, Dict, Tuple

from . import api

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# --------------------------------------------------------------------------
# Pure routing (unit-testable, framework-free)
# --------------------------------------------------------------------------
def dispatch(
    method: str,
    path: str,
    body: Dict[str, Any] | None = None,
    query: Dict[str, str] | None = None,
) -> Tuple[int, Dict[str, Any]]:
    """Route an API call to the core. Returns ``(status_code, payload)``."""
    body = body or {}
    query = query or {}
    method = method.upper()
    try:
        if method == "GET" and path == "/api/health":
            return 200, api.health()
        if method == "POST" and path == "/api/repositories/select":
            return 200, api.select_repository(str(body.get("path", "")))
        if method == "POST" and path == "/api/repositories/validate":
            return 200, api.validate_repository_path(str(body.get("path", "")))
        if method == "POST" and path == "/api/demo/load":
            return 200, api.load_demo_mode(str(body.get("pack", "small")))
        if method == "GET" and path == "/api/demo/packs":
            return 200, api.list_demo_packs()
        if method == "POST" and path == "/api/demo/export-bundle":
            return 200, api.export_demo_bundle()
        if method == "POST" and path == "/api/analytics/event":
            return 200, api.track_analytics_event(str(body.get("event", "")), **{k: v for k, v in body.items() if k != "event"})
        if method == "GET" and path == "/api/analytics/summary":
            return 200, api.analytics_overview()
        if method == "POST" and path == "/api/repositories/scan":
            return 200, api.scan_repository(body.get("path"))
        if method == "GET" and path == "/api/repositories/current/summary":
            return 200, api.current_summary()
        if method == "GET" and path == "/api/repositories/current/graph":
            return 200, api.current_graph(str(query.get("view", "module")))
        if method == "GET" and path == "/api/repositories/current/timeline":
            return 200, api.current_timeline()
        if method == "GET" and path == "/api/repositories/current/tour":
            return 200, api.current_tour(str(query.get("view", "module")))
        if method == "GET" and path == "/api/repositories/current/module":
            return 200, api.module_inspector(str(query.get("target", "")))
        if method == "GET" and path == "/api/repositories/current/risks":
            return 200, api.current_risks()
        if method == "POST" and path == "/api/impact":
            return 200, api.impact(str(body.get("target", "")))
        if method == "POST" and path == "/api/bug-investigation":
            return 200, api.bug_investigation(str(body.get("text", "")))
        if method == "POST" and path == "/api/context/export":
            return 200, api.context_export(str(body.get("target", "claude")), str(body.get("packet", "compact")))
        if method == "POST" and path == "/api/copilot/ask":
            return 200, api.copilot_ask(
                str(body.get("question", "")),
                str(body.get("target", "none")),
                str(body.get("packet", "compact")),
                node_context=body.get("node_context"),
            )
        return 404, {"ok": False, "error": f"Unknown endpoint: {method} {path}"}
    except Exception as exc:  # never 500 the desktop app silently
        return 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


ROUTES = (
    ("GET", "/api/health"),
    ("POST", "/api/repositories/select"),
    ("POST", "/api/repositories/validate"),
    ("POST", "/api/demo/load"),
    ("GET", "/api/demo/packs"),
    ("POST", "/api/demo/export-bundle"),
    ("POST", "/api/analytics/event"),
    ("GET", "/api/analytics/summary"),
    ("POST", "/api/repositories/scan"),
    ("GET", "/api/repositories/current/summary"),
    ("GET", "/api/repositories/current/graph"),
    ("GET", "/api/repositories/current/timeline"),
    ("GET", "/api/repositories/current/tour"),
    ("GET", "/api/repositories/current/module"),
    ("GET", "/api/repositories/current/risks"),
    ("POST", "/api/impact"),
    ("POST", "/api/bug-investigation"),
    ("POST", "/api/context/export"),
    ("POST", "/api/copilot/ask"),
)


# --------------------------------------------------------------------------
# stdlib HTTP handler (default runtime)
# --------------------------------------------------------------------------
class JarvisHandler(BaseHTTPRequestHandler):
    server_version = "JARVISDesktop/112"

    def log_message(self, *args: Any) -> None:  # quiet console
        pass

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self) -> None:
        rel = self.path.split("?", 1)[0].lstrip("/")
        if rel in ("", "index.html"):
            rel = "index.html"
        target = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not target.startswith(os.path.abspath(STATIC_DIR)) or not os.path.isfile(target):
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        with open(target, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route_api(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query_items = parse_qs(parsed.query or "")
        query = {key: values[0] for key, values in query_items.items() if values}
        status, payload = dispatch(self.command, path, self._read_body() if self.command == "POST" else None, query)
        self._send_json(status, payload)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0].startswith("/api/"):
            self._route_api()
        else:
            self._serve_static()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0].startswith("/api/"):
            self._route_api()
        else:
            self._send_json(404, {"ok": False, "error": "not found"})


def run(host: str = "127.0.0.1", port: int = 8777, *, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer((host, port), JarvisHandler)
    url = f"http://{host}:{port}/"
    print(f"  JARVIS Desktop — Repository Intelligence Platform")
    print(f"  Serving at {url}  (Ctrl+C to stop)")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------
# Optional FastAPI app (only if fastapi is installed)
# --------------------------------------------------------------------------
def create_fastapi_app():  # pragma: no cover - exercised only when fastapi present
    """Return a FastAPI app exposing the same routes. Requires `pip install fastapi uvicorn`."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="JARVIS Desktop", version=api.PRODUCT_VERSION)

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            return await request.json()
        except Exception:
            return {}

    @app.get("/api/health")
    def _health():
        return api.health()

    @app.post("/api/repositories/select")
    async def _select(request: Request):
        return api.select_repository(str((await _body(request)).get("path", "")))

    @app.post("/api/repositories/validate")
    async def _validate(request: Request):
        return api.validate_repository_path(str((await _body(request)).get("path", "")))

    @app.post("/api/demo/load")
    async def _demo(request: Request):
        return api.load_demo_mode(str((await _body(request)).get("pack", "small")))

    @app.get("/api/demo/packs")
    def _demo_packs():
        return api.list_demo_packs()

    @app.post("/api/demo/export-bundle")
    def _demo_bundle():
        return api.export_demo_bundle()

    @app.post("/api/analytics/event")
    async def _analytics_event(request: Request):
        b = await _body(request)
        return api.track_analytics_event(str(b.get("event", "")), **{k: v for k, v in b.items() if k != "event"})

    @app.get("/api/analytics/summary")
    def _analytics_summary():
        return api.analytics_overview()

    @app.post("/api/repositories/scan")
    async def _scan(request: Request):
        return api.scan_repository((await _body(request)).get("path"))

    @app.get("/api/repositories/current/summary")
    def _summary():
        return api.current_summary()

    @app.get("/api/repositories/current/graph")
    def _graph(view: str = "module"):
        return api.current_graph(view)

    @app.get("/api/repositories/current/timeline")
    def _timeline():
        return api.current_timeline()

    @app.get("/api/repositories/current/tour")
    def _tour(view: str = "module"):
        return api.current_tour(view)

    @app.get("/api/repositories/current/module")
    def _module(target: str = ""):
        return api.module_inspector(target)

    @app.get("/api/repositories/current/risks")
    def _risks():
        return api.current_risks()

    @app.post("/api/impact")
    async def _impact(request: Request):
        return api.impact(str((await _body(request)).get("target", "")))

    @app.post("/api/bug-investigation")
    async def _bug(request: Request):
        return api.bug_investigation(str((await _body(request)).get("text", "")))

    @app.post("/api/context/export")
    async def _ctx(request: Request):
        b = await _body(request)
        return api.context_export(str(b.get("target", "claude")), str(b.get("packet", "compact")))

    @app.post("/api/copilot/ask")
    async def _copilot(request: Request):
        b = await _body(request)
        return api.copilot_ask(
            str(b.get("question", "")),
            str(b.get("target", "none")),
            str(b.get("packet", "compact")),
            node_context=b.get("node_context"),
        )

    @app.get("/")
    def _index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
