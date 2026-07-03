"""Smoke test for the Atlas MCP server (canonical runtime).

Spawns ``py -m atlas_desktop.mcp_server`` and drives it over stdio with real JSON-RPC:
initialize -> tools/list -> scan -> a few tools/call. Exits non-zero on failure.

It validates the SHIPPING server (`atlas_desktop/mcp_server/runtime.py`). Notes where the
runtime diverges from the Part 2 design spec (`docs/MCP_SERVER_DESIGN.md`) are marked DIVERGENCE.

Usage:
    py scripts/mcp_smoke_test.py [repo_path]   # default: bundled demo repo (fast)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CANDIDATES = [
    os.path.join(REPO_ROOT, "external_repos", "requests"),
    os.path.join(REPO_ROOT, "atlas_desktop", "demo", "medium_repo"),
    os.path.join(REPO_ROOT, "atlas_desktop", "demo", "small_repo"),
]
DEFAULT_REPO = next((p for p in _DEFAULT_CANDIDATES if os.path.isdir(p)), _DEFAULT_CANDIDATES[0])


class Client:
    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def _read(self) -> dict:
        # Framing-aware: handle newline-delimited JSON (MCP stdio spec) AND LSP-style
        # Content-Length framing. NOTE/DIVERGENCE: the runtime emits Content-Length; the
        # MCP stdio standard is newline-delimited, so real-client compatibility must be
        # validated separately (see docs/MCP_SERVER_DESIGN.md).
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"no response; stderr:\n{self.proc.stderr.read()}")
        stripped = line.strip()
        if stripped.lower().startswith("content-length:"):
            n = int(stripped.split(":", 1)[1].strip())
            while True:
                if self.proc.stdout.readline().strip() == "":
                    break
            return json.loads(self.proc.stdout.read(n))
        return json.loads(stripped)

    def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        return self._read()

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def tool(self, name: str, arguments: dict) -> dict:
        resp = self.call("tools/call", {"name": name, "arguments": arguments})
        result = resp.get("result") or {}
        content = result.get("content") or []
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result


def _find_key(obj, key):
    """Recursively find the first value for `key` in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def main() -> int:
    repo = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPO
    if not os.path.isdir(repo):
        print(f"FAIL: test repo not found: {repo}")
        return 2
    # Repo-appropriate probe query/target: the requests checkout when present,
    # otherwise the bundled demo repo shipped with Atlas.
    if os.path.basename(repo) == "requests":
        probe_query, probe_target = "session cookie handling", "src/requests/sessions.py"
    else:
        probe_query, probe_target = "api request handlers", "api/handlers.py"

    proc = subprocess.Popen(
        [sys.executable, "-m", "atlas_desktop.mcp_server"],
        cwd=REPO_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=dict(os.environ),
    )
    client = Client(proc)
    failures = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    try:
        init = (client.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                           "clientInfo": {"name": "smoke", "version": "0"}}).get("result") or {})
        check("initialize returns serverInfo", str(init.get("serverInfo", {}).get("name", "")).startswith("atlas"), str(init))
        client.notify("notifications/initialized")

        resp = client.call("tools/list")
        tools = [t["name"] for t in (resp.get("result") or {}).get("tools", [])]
        expected = {"atlas_scan_repo", "atlas_get_codebase_map", "atlas_build_context_pack",
                    "atlas_what_breaks", "atlas_plan_change", "atlas_find_file", "atlas_repo_health"}
        check("tools/list exposes all 7 tools", expected.issubset(set(tools)), f"got {tools}")

        # Error contract: missing required arg -> structured error.
        payload = client.tool("atlas_build_context_pack", {})
        check("missing-arg returns structured error", payload.get("ok") is False and bool(payload.get("error")), str(payload)[:200])

        # Scan first (runtime requires an explicit scan; DIVERGENCE: design doc auto-scans).
        payload = client.tool("atlas_scan_repo", {"repo_path": repo})
        check("atlas_scan_repo ok", payload.get("ok") is True, str(payload)[:300])
        check("scan reports modules", (_find_key(payload, "module_count") or 0) > 0, str(payload)[:200])

        # Headline tool.
        payload = client.tool("atlas_build_context_pack",
                              {"task": "add retry with exponential backoff to the HTTP adapter", "max_files": 8})
        files = [f["path"] for f in (payload.get("recommended_files") or [])]
        check("context pack ok", payload.get("ok") is True, str(payload)[:300])
        check("context pack returns files", len(files) > 0, str(files))
        check("context pack has confidence", payload.get("confidence") in {"HIGH", "MEDIUM", "LOW"}, str(payload.get("confidence")))
        print(f"     -> top files: {files[:3]}  confidence={payload.get('confidence')}  tokens={payload.get('token_estimate')}")

        payload = client.tool("atlas_find_file", {"query": probe_query, "max_files": 5})
        results = payload.get("matches") or payload.get("files") or []
        check("find_file returns ranked results", payload.get("ok") is True and len(results) > 0, str(payload)[:200])

        # DIVERGENCE: runtime takes a single `target`, design spec takes `changed_files[]`.
        payload = client.tool("atlas_what_breaks", {"target": probe_target})
        check("what_breaks ok", payload.get("ok") is True, str(payload)[:200])

        payload = client.tool("atlas_repo_health", {})
        check("repo_health ok", payload.get("ok") is True, str(payload)[:200])
        blob = json.dumps(payload).lower()
        check("repo_health leaks no secrets", not any(k in blob for k in ["api_key", "secret", "password", "sk_live", "sk_test", "resend"]), "secret-like key present")

        client.call("shutdown")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    print()
    if failures:
        print(f"SMOKE TEST FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("SMOKE TEST PASSED: all checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
