"""Local desktop server for Atlas Desktop.

Default: a zero-dependency ``http.server`` app (always runs on Windows). The HTTP
routing is a thin wrapper over :func:`dispatch`, a pure function that tests call
directly (no sockets, no web framework). An optional FastAPI app is provided for
those who install fastapi/uvicorn, but it is **not** required.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any, Callable, Dict, Optional, Tuple

from . import accounts_client, api, system_browse
from . import accounts_service_runner
from . import runtime_startup
from .billing import service as billing_service
from .accounts_routes import ACCOUNTS_ROUTES

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
RouteHandler = Callable[[Dict[str, Any], Dict[str, str]], Dict[str, Any]]
PROTECTED_ACCOUNT_ROUTES = {
    ("POST", "/api/demo/load"),
    ("POST", "/api/repositories/scan"),
    ("POST", "/api/impact"),
    ("POST", "/api/planning/change"),
    ("POST", "/api/planning/investigate"),
    ("POST", "/api/planning/impact"),
    ("POST", "/api/bug-investigation"),
    ("POST", "/api/context/export"),
    ("POST", "/api/integrations/export"),
    ("POST", "/api/integrations/cursor/write-rule"),
    ("POST", "/api/integrations/claude-code/write-managed-block"),
    ("POST", "/api/copilot/ask"),
}


def _favicon_path() -> Optional[str]:
    """Return the packaged Atlas icon used for the browser favicon, if present."""
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        # Installed PyInstaller layout: {app}\assets\atlas.ico while this file
        # lives under {app}\_internal\atlas_desktop.
        os.path.join(here, "..", "..", "assets", "atlas.ico"),
        # Source/dev layout.
        os.path.join(here, "..", "packaging", "installer", "assets", "atlas.ico"),
        # Frozen internal-data fallback, if a future spec includes installer assets.
        os.path.join(here, "..", "packaging", "installer", "assets", "atlas.ico"),
    ]
    for candidate in candidates:
        path = os.path.abspath(candidate)
        if os.path.isfile(path):
            return path
    return None


class AtlasHTTPServer(ThreadingHTTPServer):
    """Own a loopback port exclusively, including on Windows."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _account_gate_failure() -> Optional[Dict[str, Any]]:
    """Return a 403 payload when local workflow access should block."""
    state = accounts_client.get_account_state()
    license_status = state.get("license") or {}
    user = state.get("user")
    if user and license_status.get("valid") is not True:
        return {
            "ok": False,
            "code": "license_required",
            "error": "Atlas account license is not active.",
            "license": license_status,
        }
    if not accounts_client.has_local_workflow_access(state):
        return {
            "ok": False,
            "code": "account_required",
            "error": "Sign in or continue locally without an account to use this workflow.",
            "license": license_status,
        }
    return None


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


def _parse_loopback_authority(value: str) -> Optional[Tuple[str, int]]:
    """Parse a loopback Host/authority with an explicit port."""
    raw = (value or "").strip()
    if not raw or "," in raw or "@" in raw:
        return None
    try:
        parsed = urlparse(f"//{raw}")
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    if (
        not hostname
        or port is None
        or not _is_loopback_host(hostname)
        or parsed.username
        or parsed.password
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        return None
    return hostname, int(port)


def _parse_loopback_origin(value: str) -> Optional[Tuple[str, int]]:
    """Parse an HTTP Origin containing only a loopback authority."""
    raw = (value or "").strip()
    try:
        parsed = urlparse(raw)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "http"
        or not hostname
        or port is None
        or not _is_loopback_host(hostname)
        or parsed.username
        or parsed.password
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        return None
    return hostname, int(port)


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
        ("POST", "/api/demo/load"): lambda body, _query: api.load_demo_mode(str(body.get("pack", "medium"))),
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
        ("GET", "/api/system/self-test"): lambda _body, _query: api.installer_self_test(),
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
        ("GET", "/api/repositories/recent"): lambda _body, _query: api.list_recent_repositories(),
        ("POST", "/api/repositories/resume"): lambda body, _query: api.resume_persisted_repository(str(body.get("repo_id", ""))),
        ("GET", "/api/history"): lambda _body, query: api.list_workflow_history_api(
            query.get("repo_id") or None,
            query.get("workflow_type") or None,
        ),
        ("GET", "/api/history/item"): lambda _body, query: api.get_workflow_history_item_api(str(query.get("history_id", ""))),
        ("GET", "/api/repositories/current/summary"): lambda _body, _query: api.current_summary(),
        ("GET", "/api/repositories/current/session-export"): lambda _body, _query: api.session_export_packet(),
        ("GET", "/api/repositories/current/trust-status"): lambda _body, _query: api.trust_integrity_status(),
        ("POST", "/api/repositories/current/refresh-changed-files"): lambda body, _query: api.refresh_changed_files(
            body.get("paths") or body.get("files")
        ),
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
        # Phase 175B — product completion
        ("GET", "/api/product/config"): lambda _body, _query: api.product_config(),
        ("GET", "/api/product/update-check"): lambda _body, _query: api.check_product_update(),
        ("GET", "/api/integrations/claude/config"): lambda _body, _query: api.agent_integrations_status(),
        ("POST", "/api/integrations/claude/test"): lambda _body, _query: api.test_claude_mcp_runtime(),
        ("POST", "/api/integrations/export"): lambda body, _query: api.agent_export(
            str(body.get("target", "claude")),
            str(body.get("task", "")),
            int(body.get("max_files") or 12),
        ),
        ("POST", "/api/integrations/cursor/write-rule"): lambda body, _query: api.write_cursor_rule(
            str(body.get("task", ""))
        ),
        ("POST", "/api/integrations/claude-code/write-managed-block"): lambda body, _query: api.write_claude_code_block(
            str(body.get("task", ""))
        ),
        ("POST", "/api/feedback"): lambda body, _query: api.submit_feedback(body or {}),
        # Phase 189 — result feedback funnel
        ("POST", "/api/feedback/result"): lambda body, _query: api.submit_result_feedback(body or {}),
        ("GET", "/api/integrations/mcp/status"): lambda _body, _query: api.mcp_setup_status(),
        ("GET", "/api/integrations/claude/config"): lambda _body, _query: api.agent_integrations_status(),
        ("POST", "/api/integrations/cursor/write-config"): lambda body, _query: api.write_cursor_mcp_config(
            body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        ),
        ("POST", "/api/integrations/claude/write-config"): lambda body, _query: api.write_claude_mcp_config(
            body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        ),
        ("POST", "/api/integrations/codex/write-config"): lambda body, _query: api.write_codex_mcp_config(
            body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        ),
        ("POST", "/api/integrations/mcp/test"): lambda _body, _query: api.test_claude_mcp_runtime(),
        ("POST", "/api/integrations/mcp/diagnostics"): lambda _body, _query: api.run_mcp_diagnostics(),
        ("GET", "/api/operations/result-feedback"): lambda _body, _query: api.operations_result_feedback_inbox(),
        # Phase 182 — beta operations foundation
        ("GET", "/api/system/identity"): lambda _body, _query: api.system_identity(),
        ("GET", "/api/operations/identity"): lambda _body, _query: api.operations_identity(),
        ("GET", "/api/operations/insights"): lambda _body, _query: api.operations_insights(),
        ("GET", "/api/operations/feedback"): lambda _body, _query: api.operations_feedback_inbox(),
        ("GET", "/api/operations/token-savings"): lambda _body, _query: api.operations_token_savings(),
        ("GET", "/api/operations/crashes"): lambda _body, _query: api.operations_crashes(),
        ("POST", "/api/operations/crash"): lambda body, _query: api.operations_record_crash(body or {}),
        # Phase 186 — accounts & access
        **ACCOUNTS_ROUTES,
    }


ROUTES = tuple(sorted((*_route_handlers().keys(), ("GET", runtime_startup.HANDSHAKE_PATH))))


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
    if (method, path) == ("GET", runtime_startup.HANDSHAKE_PATH):
        return 400, {
            "ok": False,
            "code": "http_context_required",
            "error": "The Atlas runtime handshake requires the active HTTP listener context.",
        }
    handler = _route_handlers().get((method, path))
    try:
        if handler is None:
            return 404, {"ok": False, "error": f"Unknown endpoint: {method} {path}"}
        if (method, path) in PROTECTED_ACCOUNT_ROUTES:
            blocked = _account_gate_failure()
            if blocked:
                return 403, blocked
        result = handler(body, query)
        # Phase 137A: record product usage (local/mock). Never affects the response.
        billing_service.record_from_dispatch(path, result, body)
        return 200, result
    except Exception as exc:  # never 500 the desktop app silently
        return 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def route_is_registered(method: str, path: str) -> bool:
    key = (method.upper(), normalize_api_path(path))
    return key == ("GET", runtime_startup.HANDSHAKE_PATH) or key in _route_handlers()


# --------------------------------------------------------------------------
# stdlib HTTP handler (default runtime)
# --------------------------------------------------------------------------
class AtlasHandler(BaseHTTPRequestHandler):
    server_version = "AtlasDesktop/119"
    _CORS_METHODS = ("GET", "POST")
    _CORS_HEADERS = frozenset({"accept", "content-type"})
    _CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)

    def log_message(self, *args: Any) -> None:  # quiet console
        pass

    def _authorize_api_request(self) -> Tuple[bool, Optional[str]]:
        """Allow only loopback clients addressing this exact runtime origin."""
        if not _is_loopback_host(str(self.client_address[0])):
            return False, None
        host = _parse_loopback_authority(str(self.headers.get("Host") or ""))
        expected_port = int(self.server.server_address[1])
        if host is None or host[1] != expected_port:
            return False, None
        origin_value = self.headers.get("Origin")
        if origin_value is None:
            return True, None
        origin = _parse_loopback_origin(str(origin_value))
        if origin is None or origin != host:
            return False, None
        return True, str(origin_value).strip()

    def _write_response(
        self,
        status: int,
        headers: Tuple[Tuple[str, str], ...],
        body: bytes = b"",
    ) -> bool:
        """Write a complete response while treating client disconnects as local cancellation."""
        try:
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            if body:
                self.wfile.write(body)
            return True
        except self._CLIENT_DISCONNECT_ERRORS:
            # The frontend uses bounded timeouts. A response abandoned by that
            # client must not emit a traceback or disturb other runtime calls.
            return False

    def _send_json(
        self,
        status: int,
        payload: Dict[str, Any],
        extra_headers: Tuple[Tuple[str, str], ...] = (),
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(data))),
            *extra_headers,
        ]
        cors_origin = getattr(self, "_atlas_cors_origin", None)
        if cors_origin:
            headers.extend(
                [
                    ("Access-Control-Allow-Origin", str(cors_origin)),
                    ("Vary", "Origin"),
                ]
            )
        self._write_response(status, tuple(headers), data)

    def _read_body(self) -> Optional[Dict[str, Any]]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                return None
            return json.loads(raw.decode("utf-8") or "{}")
        except self._CLIENT_DISCONNECT_ERRORS:
            return None
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self) -> None:
        rel = self.path.split("?", 1)[0].lstrip("/")
        if rel in ("", "index.html"):
            rel = "index.html"
        if rel == "favicon.ico":
            icon = _favicon_path()
            if icon:
                with open(icon, "rb") as fh:
                    data = fh.read()
                self._write_response(
                    200,
                    (("Content-Type", "image/x-icon"), ("Content-Length", str(len(data)))),
                    data,
                )
                return
            self._write_response(204, (("Content-Length", "0"),))
            return
        target = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not target.startswith(os.path.abspath(STATIC_DIR)) or not os.path.isfile(target):
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        with open(target, "rb") as fh:
            data = fh.read()
        self._write_response(
            200,
            (("Content-Type", ctype), ("Content-Length", str(len(data)))),
            data,
        )

    def _route_api(self) -> None:
        authorized, cors_origin = self._authorize_api_request()
        self._atlas_cors_origin = cors_origin if authorized else None
        if not authorized:
            self._send_json(
                403,
                {
                    "ok": False,
                    "code": "untrusted_runtime_origin",
                    "error": "Atlas API requests must come from this local runtime origin.",
                },
            )
            return
        parsed = urlparse(self.path)
        path = normalize_api_path(parsed.path)
        if path == runtime_startup.HANDSHAKE_PATH:
            if self.command != "GET":
                self._send_json(
                    405,
                    {
                        "ok": False,
                        "code": "method_not_allowed",
                        "error": "The Atlas runtime handshake is GET-only.",
                    },
                    (("Allow", "GET, OPTIONS"),),
                )
                return
            query_items = parse_qs(parsed.query or "")
            challenge = str((query_items.get("challenge") or [""])[0])
            identity = getattr(self.server, "atlas_runtime_identity", None) or {}
            if not challenge or not identity:
                self._send_json(400, {"ok": False, "error": "runtime handshake unavailable"})
                return
            self._send_json(
                200,
                runtime_startup.handshake_payload(
                    challenge,
                    port=int(self.server.server_address[1]),
                    pid=int(identity.get("pid") or os.getpid()),
                    instance_id=str(identity.get("instance_id") or ""),
                ),
            )
            return
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
        request_body = self._read_body() if self.command == "POST" else None
        if self.command == "POST" and request_body is None:
            return
        status, payload = dispatch(self.command, path, request_body, query)
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

    def do_OPTIONS(self) -> None:
        path = normalize_api_path(self.path.split("?", 1)[0])
        if not path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        authorized, cors_origin = self._authorize_api_request()
        self._atlas_cors_origin = cors_origin if authorized else None
        requested_method = str(self.headers.get("Access-Control-Request-Method") or "").upper()
        requested_headers = {
            item.strip().lower()
            for item in str(self.headers.get("Access-Control-Request-Headers") or "").split(",")
            if item.strip()
        }
        if path == runtime_startup.HANDSHAKE_PATH:
            route_methods = ("GET",)
        else:
            route_methods = tuple(method for method in self._CORS_METHODS if route_is_registered(method, path))
        if (
            not authorized
            or requested_method not in route_methods
            or not requested_headers.issubset(self._CORS_HEADERS)
        ):
            self._atlas_cors_origin = None
            self._send_json(
                403,
                {
                    "ok": False,
                    "code": "cors_request_rejected",
                    "error": "Atlas rejected an untrusted preflight request.",
                },
            )
            return
        response_headers = [
            ("Content-Length", "0"),
            ("Allow", ", ".join((*route_methods, "OPTIONS"))),
            ("Access-Control-Allow-Methods", ", ".join(route_methods)),
        ]
        if requested_headers:
            allowed = [name for name in ("Accept", "Content-Type") if name.lower() in requested_headers]
            response_headers.append(("Access-Control-Allow-Headers", ", ".join(allowed)))
        if cors_origin:
            response_headers.extend(
                [
                    ("Access-Control-Allow-Origin", cors_origin),
                    ("Vary", "Origin"),
                ]
            )
        self._write_response(204, tuple(response_headers))


def _log_launcher(message: str) -> None:
    """Best-effort local log; never raises."""
    try:
        from .install_support import append_launcher_log

        append_launcher_log(message)
    except Exception:
        pass


def _port_bind_retryable(exc: OSError) -> bool:
    """Treat occupied, denied, and firewall-blocked binds as retryable (175D)."""
    if isinstance(exc, PermissionError):
        return True
    win_code = getattr(exc, "winerror", None)
    if win_code in (10048, 10013):
        return True
    errno = getattr(exc, "errno", None)
    return errno in (13, 48, 98, 10048, 10013)


def _bind_http_server(host: str, port: int, *, attempts: int = 10):
    """Beta P0-03 / 175D — try alternate localhost ports when bind is blocked."""
    last_exc: Optional[Exception] = None
    start = port if port else 0
    count = 1 if port == 0 else attempts
    for offset in range(count):
        candidate = start + offset
        try:
            httpd = ThreadingHTTPServer((host, candidate), AtlasHandler)
            bound = int(httpd.server_address[1])
            return httpd, bound
        except OSError as exc:
            last_exc = exc
            if _port_bind_retryable(exc):
                _log_launcher(f"port {candidate} unavailable ({type(exc).__name__}); trying next")
                continue
            raise
    if last_exc:
        raise last_exc
    raise OSError(f"Could not bind {host}:{port}-{port + attempts - 1}")


def _select_runtime(host: str, preferred_port: int):
    """Select a safe port or reuse only a cryptographically verified Atlas."""
    last_exc: Optional[OSError] = None
    for candidate in runtime_startup.controlled_ports(preferred_port):
        try:
            httpd = AtlasHTTPServer((host, candidate), AtlasHandler)
            return httpd, int(httpd.server_address[1]), None
        except OSError as exc:
            if not _port_bind_retryable(exc):
                raise
            last_exc = exc
            if candidate == preferred_port:
                _log_launcher(
                    f"preferred port {candidate} is occupied; selecting controlled fallback without probing it"
                )
                continue
            # A concurrent process can bind immediately before it starts
            # serving. Bounded retries close that startup race.
            existing = runtime_startup.probe_atlas(host, candidate, attempts=12)
            if existing:
                _log_launcher(f"verified existing Atlas runtime on port {candidate}")
                return None, candidate, existing
            _log_launcher(
                f"port {candidate} occupied by foreign or unready service; trying controlled fallback"
            )
    if last_exc:
        raise last_exc
    raise OSError("No controlled Atlas desktop ports are available")


def _find_edge_executable() -> Optional[str]:
    found = shutil.which("msedge") or shutil.which("msedge.exe")
    if found:
        return found
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _open_url(url: str, *, mode: str = "browser") -> bool:
    mode = (mode or "browser").strip().lower()
    if mode == "app":
        edge = _find_edge_executable()
        if edge:
            try:
                subprocess.Popen(
                    [edge, f"--app={url}", "--new-window"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
                _log_launcher(f"opened app window: {url}")
                return True
            except OSError as exc:
                _log_launcher(f"edge app-window open failed: {type(exc).__name__}: {exc}")
    try:
        import webbrowser

        opened = bool(webbrowser.open(url))
        if opened:
            _log_launcher(f"opened browser: {url}")
        return opened
    except Exception as exc:  # no browser / sandbox
        _log_launcher(f"browser open failed: {type(exc).__name__}: {exc}")
        return False


def _open_after_health(host: str, port: int, url: str, *, mode: str) -> None:
    for _ in range(60):
        if runtime_startup.probe_atlas(host, port, timeout=0.5):
            break
        time.sleep(0.15)
    opened = _open_url(url, mode=mode)
    if not opened:
        _log_launcher(f"could not auto-open; visit {url} manually")
        if not getattr(sys, "frozen", False):
            print(f"  Could not auto-open Atlas. Open this URL manually:\n    {url}")


def _track_app_started() -> None:
    """Fire app_started analytics once per server launch — never raises."""
    try:
        from . import operations as _ops
        _ops.pipeline_track_event("app_started")
    except Exception:
        pass


def run(
    host: str = "127.0.0.1",
    port: int = 8777,
    *,
    open_browser: bool = True,
    open_mode: str = "browser",
    start_path: str = "/",
) -> None:
    _track_app_started()
    accounts_service_runner.ensure_running_async()
    try:
        httpd, bound_port, existing = _select_runtime(host, port)
    except OSError as exc:
        _log_launcher(f"bind failed on {host}:{port}: {type(exc).__name__}: {exc}")
        httpd, bound_port = _bind_http_server(host, 0, attempts=1)
        existing = None
        start_path = "/startup-error.html"
        _log_launcher(f"recovered on ephemeral port {bound_port} with startup-error page")
    if bound_port != port:
        _log_launcher(f"serving on alternate port {bound_port} (requested {port})")
    path = start_path if start_path.startswith("/") else f"/{start_path}"
    url = f"http://{host}:{bound_port}{path}"
    if existing:
        if open_browser:
            _open_url(url, mode=open_mode)
        return
    identity = runtime_startup.new_instance_identity(bound_port)
    httpd.atlas_runtime_identity = identity
    try:
        runtime_startup.write_runtime_descriptor(identity)
    except OSError as exc:
        _log_launcher(f"runtime descriptor write failed: {type(exc).__name__}: {exc}")
    if not getattr(__import__("sys"), "frozen", False):
        print(f"  ATLAS — Repository Intelligence Platform")
        print(f"  Serving at http://{host}:{bound_port}/  (Ctrl+C to stop)")
    if open_browser:
        threading.Thread(
            target=_open_after_health,
            args=(host, bound_port, url),
            kwargs={"mode": open_mode},
            daemon=True,
        ).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        if not getattr(__import__("sys"), "frozen", False):
            print("\n  Stopped.")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------
# Optional FastAPI app (only if fastapi is installed)
# --------------------------------------------------------------------------
def create_fastapi_app():  # pragma: no cover - exercised only when fastapi present
    """Return a FastAPI app exposing the same routes. Requires `pip install fastapi uvicorn`."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse, Response
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import ClientDisconnect

    # ``from __future__ import annotations`` stores nested endpoint annotations
    # as strings. Make FastAPI's optional Request type resolvable when this
    # compatibility app is constructed, without importing FastAPI at startup.
    globals()["Request"] = Request

    app = FastAPI(title="Atlas — Repository Intelligence Platform", version=api.PRODUCT_VERSION)
    app.state.atlas_runtime_identities = {}

    def _fastapi_route_methods(path: str) -> Tuple[str, ...]:
        """Return only methods implemented by an exact FastAPI API route."""
        methods = set()
        for route in app.routes:
            route_path = getattr(route, "path", None)
            if route_path and normalize_api_path(str(route_path)) == path:
                methods.update(str(method).upper() for method in (getattr(route, "methods", None) or ()))
        return tuple(method for method in AtlasHandler._CORS_METHODS if method in methods)

    def _fastapi_runtime_authority(request: Request) -> Tuple[bool, Optional[str], int]:
        """Authorize the ASGI request against its actual loopback listener."""
        client = request.scope.get("client") or ("", 0)
        server_address = request.scope.get("server") or ("", 0)
        try:
            client_host = str(client[0])
            listener_port = int(server_address[1])
        except (IndexError, TypeError, ValueError):
            return False, None, 0
        if not _is_loopback_host(client_host) or listener_port <= 0:
            return False, None, 0
        host = _parse_loopback_authority(str(request.headers.get("host") or ""))
        if host is None or host[1] != listener_port:
            return False, None, listener_port
        origin_value = request.headers.get("origin")
        if origin_value is None:
            return True, None, listener_port
        origin = _parse_loopback_origin(str(origin_value))
        if origin is None or origin != host:
            return False, None, listener_port
        return True, str(origin_value).strip(), listener_port

    @app.middleware("http")
    async def _enforce_runtime_transport_boundary(request: Request, call_next):
        path = normalize_api_path(str(request.scope.get("path") or request.url.path))
        if not path.startswith("/api/"):
            return await call_next(request)

        authorized, cors_origin, _listener_port = _fastapi_runtime_authority(request)
        if not authorized:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "code": "untrusted_runtime_origin",
                    "error": "Atlas API requests must come from this local runtime origin.",
                },
            )

        if request.method.upper() == "OPTIONS":
            requested_method = str(request.headers.get("access-control-request-method") or "").upper()
            requested_headers = {
                item.strip().lower()
                for item in str(request.headers.get("access-control-request-headers") or "").split(",")
                if item.strip()
            }
            route_methods = _fastapi_route_methods(path)
            if (
                requested_method not in route_methods
                or not requested_headers.issubset(AtlasHandler._CORS_HEADERS)
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "code": "cors_request_rejected",
                        "error": "Atlas rejected an untrusted preflight request.",
                    },
                )
            headers = {
                "Content-Length": "0",
                "Allow": ", ".join((*route_methods, "OPTIONS")),
                "Access-Control-Allow-Methods": ", ".join(route_methods),
            }
            if requested_headers:
                allowed = [
                    name
                    for name in ("Accept", "Content-Type")
                    if name.lower() in requested_headers
                ]
                headers["Access-Control-Allow-Headers"] = ", ".join(allowed)
            if cors_origin:
                headers["Access-Control-Allow-Origin"] = cors_origin
                headers["Vary"] = "Origin"
            return Response(status_code=204, headers=headers)

        if path == runtime_startup.HANDSHAKE_PATH and request.method.upper() != "GET":
            return JSONResponse(
                status_code=405,
                content={
                    "ok": False,
                    "code": "method_not_allowed",
                    "error": "The Atlas runtime handshake is GET-only.",
                },
                headers={"Allow": "GET, OPTIONS"},
            )

        response = await call_next(request)
        if cors_origin:
            response.headers["Access-Control-Allow-Origin"] = cors_origin
            vary = str(response.headers.get("Vary") or "")
            if "origin" not in {item.strip().lower() for item in vary.split(",") if item.strip()}:
                response.headers["Vary"] = f"{vary}, Origin".strip(", ")
        return response

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            return await request.json()
        except ClientDisconnect:
            # Never turn an abandoned state-changing request into an empty
            # payload whose endpoint defaults can still execute.
            raise
        except Exception:
            return {}

    def _account_gate_response():
        blocked = _account_gate_failure()
        if blocked:
            return JSONResponse(status_code=403, content=blocked)
        return None

    @app.get(runtime_startup.HANDSHAKE_PATH)
    def _runtime_handshake(request: Request, challenge: str = ""):
        server_address = request.scope.get("server") or ("", 0)
        try:
            port = int(server_address[1])
        except (IndexError, TypeError, ValueError):
            port = 0
        if not challenge or port <= 0:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "runtime handshake unavailable"},
            )
        identity = app.state.atlas_runtime_identities.get(port)
        if not identity:
            identity = runtime_startup.new_instance_identity(port)
            app.state.atlas_runtime_identities[port] = identity
            try:
                runtime_startup.write_runtime_descriptor(identity)
            except OSError:
                pass
        return runtime_startup.handshake_payload(
            challenge,
            port=port,
            pid=int(identity.get("pid") or os.getpid()),
            instance_id=str(identity.get("instance_id") or ""),
        )

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
        blocked = _account_gate_response()
        if blocked:
            return blocked
        return api.load_demo_mode(str((await _body(request)).get("pack", "medium")))

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
        blocked = _account_gate_response()
        if blocked:
            return blocked
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

    @app.get("/api/system/self-test")
    def _self_test():
        return api.installer_self_test()

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
        blocked = _account_gate_response()
        if blocked:
            return blocked
        return api.impact(str((await _body(request)).get("target", "")))

    @app.post("/api/planning/change")
    async def _plan_change(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
        b = await _body(request)
        return api.plan_change(str(b.get("request") or b.get("goal") or b.get("text") or ""))

    @app.post("/api/planning/investigate")
    async def _plan_investigate(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
        b = await _body(request)
        return api.investigate_symptom(str(b.get("symptom") or b.get("text") or b.get("description") or ""))

    @app.post("/api/planning/impact")
    async def _plan_impact(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
        return api.change_impact_simulation(str((await _body(request)).get("target", "")))

    @app.post("/api/bug-investigation")
    async def _bug(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
        return api.bug_investigation(str((await _body(request)).get("text", "")))

    @app.post("/api/context/export")
    async def _ctx(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
        b = await _body(request)
        return api.context_export(str(b.get("target", "claude")), str(b.get("packet", "compact")))

    @app.get("/api/integrations/mcp/status")
    def _mcp_status():
        return api.mcp_setup_status()

    @app.post("/api/integrations/cursor/write-config")
    async def _cursor_write_config(request: Request):
        body = await _body(request)
        confirm = body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        return api.write_cursor_mcp_config(confirm)

    @app.post("/api/integrations/claude/write-config")
    async def _claude_write_config(request: Request):
        body = await _body(request)
        confirm = body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        return api.write_claude_mcp_config(confirm)

    @app.post("/api/integrations/codex/write-config")
    async def _codex_write_config(request: Request):
        body = await _body(request)
        confirm = body.get("confirm") is True or str(body.get("confirm", "")).lower() in {"1", "true", "yes"}
        return api.write_codex_mcp_config(confirm)

    @app.post("/api/integrations/mcp/test")
    def _mcp_test():
        return api.test_claude_mcp_runtime()

    @app.post("/api/copilot/ask")
    async def _copilot(request: Request):
        blocked = _account_gate_response()
        if blocked:
            return blocked
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
