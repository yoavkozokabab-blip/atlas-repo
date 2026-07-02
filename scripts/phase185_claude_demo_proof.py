"""Phase 185 — capture MCP evidence for the Claude Desktop demo question.

Simulates the Atlas tool chain Claude Desktop would invoke for:
  "Where is authentication implemented?"

Writes: reports/phase185_claude_desktop_demo_evidence.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
REPORTS = REPO_ROOT / "reports"
QUESTION = "Where is authentication implemented?"


class McpClient:
    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def _read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"no MCP response; stderr:\n{self.proc.stderr.read()}")
        stripped = line.strip()
        if stripped.lower().startswith("content-length:"):
            n = int(stripped.split(":", 1)[1].strip())
            while self.proc.stdout.readline().strip() != "":
                pass
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
        content = (resp.get("result") or {}).get("content") or []
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return resp.get("result") or {}


def _make_demo_repo(root: Path) -> Path:
    repo = root / "auth_demo_repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "auth.py").write_text(
        "class AuthStore:\n    def login(self, token: str) -> bool:\n        return bool(token)\n",
        encoding="utf-8",
    )
    (repo / "app" / "routes.py").write_text(
        "from app.auth import AuthStore\n\ndef authenticate(request):\n    return AuthStore().login(request.token)\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_auth.py").write_text(
        "from app.auth import AuthStore\n\ndef test_login():\n    assert AuthStore().login('x')\n",
        encoding="utf-8",
    )
    return repo


def _synthetic_claude_answer(tool_results: list[dict]) -> str:
    files: list[str] = []
    for block in tool_results:
        payload = block.get("response") or {}
        for item in payload.get("recommended_files") or payload.get("matches") or []:
            if isinstance(item, dict):
                path = item.get("path")
            else:
                path = str(item)
            if path and path not in files:
                files.append(path)
    if files:
        top = ", ".join(f"`{p}`" for p in files[:3])
        return (
            f"Authentication is implemented in {top}. "
            "These paths were returned by Atlas MCP tools after scanning the repository."
        )
    return "Atlas MCP tools ran but did not return ranked authentication file paths."


def main() -> int:
    from jarvis_desktop import agent_integrations as ai

    proof_dir = REPORTS / "phase185_demo_workspace"
    proof_dir.mkdir(parents=True, exist_ok=True)
    demo_repo = _make_demo_repo(proof_dir)

    proc = subprocess.Popen(
        [sys.executable, "-m", "jarvis_desktop.mcp_server"],
        cwd=str(REPO_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ),
    )
    client = McpClient(proc)
    tool_trace: list[dict] = []

    try:
        client.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "phase185-proof", "version": "1"},
            },
        )
        client.notify("notifications/initialized")

        scan = client.tool("atlas_scan_repo", {"repo_path": str(demo_repo)})
        tool_trace.append({"tool": "atlas_scan_repo", "arguments": {"repo_path": str(demo_repo)}, "response": scan})

        find_file = client.tool(
            "atlas_find_file",
            {"query": QUESTION, "limit": 8, "repo_path": str(demo_repo)},
        )
        tool_trace.append(
            {
                "tool": "atlas_find_file",
                "arguments": {"query": QUESTION, "limit": 8},
                "response": find_file,
            }
        )

        find_relevant = client.tool(
            "atlas_find_relevant_files",
            {"task": QUESTION, "max_files": 8, "repo_path": str(demo_repo)},
        )
        tool_trace.append(
            {
                "tool": "atlas_find_relevant_files",
                "arguments": {"task": QUESTION, "max_files": 8},
                "response": find_relevant,
            }
        )

        client.call("shutdown")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    claude_status = ai.claude_config_status()
    evidence = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": QUESTION,
        "demo_repo": str(demo_repo),
        "claude_desktop": {
            "config_path": claude_status.get("config_path"),
            "config_source": claude_status.get("config_source"),
            "discovered_paths": claude_status.get("discovered_paths"),
            "atlas_configured": claude_status.get("atlas_configured"),
        },
        "tool_trace": tool_trace,
        "synthetic_claude_answer": _synthetic_claude_answer(tool_trace),
        "notes": (
            "Automated MCP proof. Live Claude Desktop UI interaction must be captured "
            "manually on a machine with Claude Desktop installed."
        ),
    }

    out = REPORTS / "phase185_claude_desktop_demo_evidence.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    ok = all((t.get("response") or {}).get("ok") for t in tool_trace)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
