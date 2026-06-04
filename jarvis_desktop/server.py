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
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any, Callable, Dict, Tuple

from . import api, system_browse
from .billing import service as billing_service

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
RouteHandler = Callable[[Dict[str, Any], Dict[str, str]], Dict[str, Any]]


def _is_loopback_host(host: str) -> bool:
    """Return whether an HTTP client host is local to this machine."""
    try:
        return ip_address((host or "").split("%", 1)[0]).is_loopback
    except ValueError:
        return (host or "").lower() == "localhost"


def normalize_api_path(path: str) -> str:
    """Normalize request paths so `/api/foo` and `/api/foo/` resolve identically."""
    cleaned = (path or "/").split("?", 1)[0].strip()
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    if cleaned != "/":
        cleaned = cleaned.rstrip("/")
    return cleaned or "/"


def _route_handlers() -> Dict[Tuple[str, str], RouteHandler]:
    """Single source of truth for API routing (stdlib + tests + route audit)."""

    def _analytics_event(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        props = {k: v for k, v in body.items() if k != "event"}
        return api.track_analytics_event(str(body.get("event", "")), **props)

    def _copilot(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        return api.copilot_ask(
            str(body.get("question", "")),
            str(body.get("target", "none")),
            str(body.get("packet", "compact")),
            node_context=body.get("node_context"),
        )

    def _planning_change(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        request = body.get("request") or body.get("goal") or body.get("text") or ""
        return api.plan_change(str(request))

    def _planning_investigate(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        symptom = body.get("symptom") or body.get("text") or body.get("description") or ""
        return api.investigate_symptom(str(symptom))

    def _planning_impact(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        return api.change_impact_simulation(str(body.get("target", "")))

    def _usage_event(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
        return api.usage_post_event(body)

    return {
        ("GET", "/api/health"): lambda _body, _query: api.health(),
        ("POST", "/api/system/browse-folder"): lambda _body, _query: system_browse.browse_folder(),
        ("POST", "/api/repositories/select"): lambda body, _query: api.select_repository(str(body.get("path", ""))),
        ("POST", "/api/repositories/validate"): lambda body, _query: api.validate_repository_path(str(body.get("path", ""))),
        ("POST", "/api/repositories/estimate"): lambda body, _query: api.pre_scan_estimate(str(body.get("path", "")), body.get("scope")),
        ("POST", "/api/demo/load"): lambda body, _query: api.load_demo_mode(str(body.get("pack", "small"))),
        ("GET", "/api/demo/packs"): lambda _body, _query: api.list_demo_packs(),
        ("POST", "/api/demo/export-bundle"): lambda _body, _query: api.export_demo_bundle(),
        ("POST", "/api/analytics/event"): _analytics_event,
        ("GET", "/api/analytics/summary"): lambda _body, _query: api.analytics_overview(),
        ("POST", "/api/repositories/scan"): lambda body, _query: api.scan_repository(body.get("path"), body.get("scope")),
        ("GET", "/api/repositories/current/scan-status"): lambda _body, _query: api.scan_status(),
        ("GET", "/api/repositories/current/scan-performance"): lambda _body, _query: api.current_scan_performance(),
        ("GET", "/api/repositories/current/system-health"): lambda _body, _query: api.beta_system_health(),
        ("GET", "/api/system/diagnostics"): lambda _body, _query: api.beta_diagnostics(),
        ("GET", "/api/system/startup-status"): lambda _body, _query: api.startup_status(),
        ("POST", "/api/system/clear-cache"): lambda _body, _query: api.clear_scan_cache(),
        ("POST", "/api/system/rebuild-index"): lambda body, _query: api.rebuild_repository_index(
            rescan=body.get("rescan", True) is not False
        ),
        ("POST", "/api/system/support-bundle"): lambda _body, _query: api.export_support_bundle(),
        ("POST", "/api/repositories/current/cancel-scan"): lambda _body, _query: api.cancel_scan(),
        ("POST", "/api/repositories/current/build-full-graph"): lambda _body, _query: api.build_full_module_graph(),
        ("POST", "/api/repositories/diagnostics/scan"): lambda body, _query: api.run_scan_diagnostic(
            str(body.get("path", "")),
            scope=body.get("scope"),
            output_path=str(body.get("output_path", "")) or None,
            timeout_sec=float(body.get("timeout_sec")) if body.get("timeout_sec") is not None else None,
        ),
        ("GET", "/api/repositories/current/summary"): lambda _body, _query: api.current_summary(),
        ("GET", "/api/repositories/current/graph"): lambda _body, query: api.current_graph(
            str(query.get("view", "module")),
            force_module=str(query.get("force_module", "0")).lower() in {"1", "true", "yes"},
        ),
        ("GET", "/api/repositories/current/hierarchy-graph"): lambda _body, query: api.current_hierarchy_graph(
            str(query.get("level", "subsystem")),
            str(query.get("parent", "")),
        ),
        ("GET", "/api/repositories/current/timeline"): lambda _body, _query: api.current_timeline(),
        ("GET", "/api/repositories/current/tour"): lambda _body, query: api.current_tour(str(query.get("view", "module"))),
        ("GET", "/api/repositories/current/module"): lambda _body, query: api.module_inspector(str(query.get("target", ""))),
        ("GET", "/api/repositories/current/risks"): lambda _body, _query: api.current_risks(),
        ("POST", "/api/impact"): lambda body, _query: api.impact(str(body.get("target", ""))),
        ("POST", "/api/planning/change"): _planning_change,
        ("POST", "/api/planning/investigate"): _planning_investigate,
        ("POST", "/api/planning/impact"): _planning_impact,
        ("POST", "/api/bug-investigation"): lambda body, _query: api.bug_investigation(str(body.get("text", ""))),
        ("POST", "/api/context/export"): lambda body, _query: api.context_export(
            str(body.get("target", "claude")),
            str(body.get("packet", "compact")),
        ),
        ("POST", "/api/copilot/ask"): _copilot,
        # Phase 137A — usage / billing-ready (local/mock, no Stripe)
        ("GET", "/api/usage/me"): lambda _body, _query: api.usage_me(),
        ("GET", "/api/usage/admin"): lambda _body, _query: api.usage_admin(),
        ("GET", "/api/usage/admin_summary"): lambda _body, _query: api.usage_admin(),
        ("GET", "/api/plans"): lambda _body, _query: api.usage_plans(),
        ("GET", "/api/pricing"): lambda _body, _query: api.usage_pricing(),
        ("POST", "/api/usage/event"): _usage_event,
        ("GET", "/api/billing/config"): lambda _body, _query: billing_service.billing_config(),
        ("GET", "/api/billing/plans"): lambda _body, _query: api.usage_plans(),
        ("GET", "/api/billing/usage"): lambda _body, _query: api.usage_me(),
        ("GET", "/api/billing/admin"): lambda _body, _query: api.usage_admin(),
    }


ROUTES = tuple(sorted(_route_handlers().keys()))


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
    path = normalize_api_path(path)
    handler = _route_handlers().get((method, path))
    try:
        if handler is None:
            return 404, {"ok": False, "error": f"Unknown endpoint: {method} {path}"}
        result = handler(body, query)
        # Phase 137A: record product usage (local/mock). Never affects the response.
        billing_service.record_from_dispatch(path, result, body)
        return 200, result
    except Exception as exc:  # never 500 the desktop app silently
        return 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def route_is_registered(method: str, path: str) -> bool:
    return (method.upper(), normalize_api_path(path)) in _route_handlers()


# --------------------------------------------------------------------------
# stdlib HTTP handler (default runtime)
# --------------------------------------------------------------------------
class JarvisHandler(BaseHTTPRequestHandler):
    server_version = "SyronDesktop/119"

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
        path = normalize_api_path(parsed.path)
        if path == "/api/system/browse-folder" and not _is_loopback_host(str(self.client_address[0])):
            self._send_json(
                403,
                {
                    "ok": False,
                    "supported": False,
                    "cancelled": False,
                    "code": "localhost_required",
                    "error": "Native folder selection is available only from localhost.",
                },
            )
            return
        query_items = parse_qs(parsed.query or "")
        query = {key: values[0] for key, values in query_items.items() if values}
        status, payload = dispatch(self.command, path, self._read_body() if self.command == "POST" else None, query)
        self._send_json(status, payload)

    def do_GET(self) -> None:
        if normalize_api_path(self.path.split("?", 1)[0]).startswith("/api/"):
            self._route_api()
        else:
            self._serve_static()

    def do_POST(self) -> None:
        if normalize_api_path(self.path.split("?", 1)[0]).startswith("/api/"):
            self._route_api()
        else:
            self._send_json(404, {"ok": False, "error": "not found"})


def run(
    host: str = "127.0.0.1",
    port: int = 8777,
    *,
    open_browser: bool = True,
    start_path: str = "/",
) -> None:
    httpd = ThreadingHTTPServer((host, port), JarvisHandler)
    path = start_path if start_path.startswith("/") else f"/{start_path}"
    url = f"http://{host}:{port}{path}"
    print(f"  ATLAS — Repository Intelligence Platform")
    print(f"  Serving at http://{host}:{port}/  (Ctrl+C to stop)")
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

    app = FastAPI(title="Syron — Repository Intelligence Platform", version=api.PRODUCT_VERSION)

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            return await request.json()
        except Exception:
            return {}

    @app.get("/api/health")
    def _health():
        return api.health()

    @app.post("/api/system/browse-folder")
    def _browse_folder(request: Request):
        client_host = request.client.host if request.client else ""
        if not _is_loopback_host(client_host):
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "supported": False,
                    "cancelled": False,
                    "code": "localhost_required",
                    "error": "Native folder selection is available only from localhost.",
                },
            )
        return system_browse.browse_folder()

    @app.post("/api/repositories/select")
    async def _select(request: Request):
        return api.select_repository(str((await _body(request)).get("path", "")))

    @app.post("/api/repositories/validate")
    async def _validate(request: Request):
        return api.validate_repository_path(str((await _body(request)).get("path", "")))

    @app.post("/api/repositories/estimate")
    async def _estimate(request: Request):
        b = await _body(request)
        return api.pre_scan_estimate(str(b.get("path", "")), b.get("scope"))

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
        b = await _body(request)
        return api.scan_repository(b.get("path"), b.get("scope"))

    @app.get("/api/repositories/current/scan-status")
    def _scan_status():
        return api.scan_status()

    @app.get("/api/repositories/current/scan-performance")
    def _scan_performance():
        return api.current_scan_performance()

    @app.get("/api/repositories/current/system-health")
    def _system_health():
        return api.beta_system_health()

    @app.get("/api/system/diagnostics")
    def _beta_diagnostics():
        return api.beta_diagnostics()

    @app.get("/api/system/startup-status")
    def _startup_status():
        return api.startup_status()

    @app.post("/api/system/clear-cache")
    def _clear_cache():
        return api.clear_scan_cache()

    @app.post("/api/system/rebuild-index")
    async def _rebuild_index(request: Request):
        body = await _body(request)
        return api.rebuild_repository_index(rescan=body.get("rescan", True) is not False)

    @app.post("/api/system/support-bundle")
    def _support_bundle():
        return api.export_support_bundle()

    @app.post("/api/repositories/current/cancel-scan")
    def _cancel_scan():
        return api.cancel_scan()

    @app.get("/api/repositories/current/summary")
    def _summary():
        return api.current_summary()

    @app.get("/api/repositories/current/graph")
    def _graph(view: str = "module", force_module: bool = False):
        return api.current_graph(view, force_module=force_module)

    @app.get("/api/repositories/current/hierarchy-graph")
    def _hierarchy_graph(level: str = "subsystem", parent: str = ""):
        return api.current_hierarchy_graph(level, parent)

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

    @app.post("/api/planning/change")
    async def _plan_change(request: Request):
        b = await _body(request)
        return api.plan_change(str(b.get("request") or b.get("goal") or b.get("text") or ""))

    @app.post("/api/planning/investigate")
    async def _plan_investigate(request: Request):
        b = await _body(request)
        return api.investigate_symptom(str(b.get("symptom") or b.get("text") or b.get("description") or ""))

    @app.post("/api/planning/impact")
    async def _plan_impact(request: Request):
        return api.change_impact_simulation(str((await _body(request)).get("target", "")))

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

    @app.get("/api/usage/me")
    def _usage_me():
        return api.usage_me()

    @app.get("/api/usage/admin")
    def _usage_admin():
        return api.usage_admin()

    @app.get("/api/usage/admin_summary")
    def _usage_admin_summary():
        return api.usage_admin()

    @app.get("/api/plans")
    def _plans():
        return api.usage_plans()

    @app.get("/api/pricing")
    def _pricing():
        return api.usage_pricing()

    @app.post("/api/usage/event")
    async def _usage_event_route(request: Request):
        return api.usage_post_event(await _body(request))

    @app.get("/")
    def _index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
