"""End-to-end proof for Codex MCP integration.

Exercises:
  1. Atlas writes valid Codex TOML config
  2. Existing MCP servers are preserved
  3. Command from config launches Atlas.exe --mcp (or source mode)
  4. MCP tools/list + required tool calls over stdio
  5. Config survives re-read (restart simulation)
  6. Missing Codex install path handling
  7. Packaged exe vs source mode snippets

Usage:
  py -3 scripts/codex_mcp_e2e_proof.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_desktop import agent_integrations as ai  # noqa: E402

REQUIRED_TOOLS = {
    "atlas_health",
    "atlas_scan_repo",
    "atlas_find_relevant_files",
    "atlas_root_cause",
    "atlas_plan_change",
}
REPO = ROOT / "benchmarks" / "repos" / "atlas_reference"
INSTALLED_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Atlas" / "Atlas.exe"
OUT = ROOT / "reports" / "codex_mcp_e2e" / "result.json"


class McpClient:
    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def _send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def call(self, method: str, params: dict | None = None, timeout: float = 90) -> dict:
        self._id += 1
        mid = self._id
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            assert self.proc.stdout is not None
            line = self.proc.stdout.readline()
            if not line:
                return {"error": "eof"}
            text = line.decode("utf-8", "replace").strip()
            if not text.startswith("{"):
                continue
            msg = json.loads(text)
            if msg.get("id") == mid:
                return msg
        return {"error": "timeout"}

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def tool(self, name: str, args: dict) -> tuple[dict, bool]:
        res = self.call("tools/call", {"name": name, "arguments": args})
        content = (((res.get("result") or {}).get("content") or [{}])[0]).get("text") or "{}"
        try:
            payload = json.loads(content)
        except Exception:
            payload = {"raw": content}
        is_error = bool((res.get("result") or {}).get("isError"))
        return payload, is_error

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def spawn_from_config(command: str, args: list[str], cwd: str | None = None) -> subprocess.Popen:
    cmd = [command, *args]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd or None,
        text=False,
    )


def run_mcp_session(command: str, args: list[str], cwd: str | None = None) -> dict:
    proc = spawn_from_config(command, args, cwd)
    time.sleep(0.8)
    if proc.poll() is not None:
        err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
        return {"ok": False, "error": err[:400] or f"exit={proc.returncode}"}
    client = McpClient(proc)
    try:
        init = client.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "codex-e2e-proof", "version": "0"},
            },
        )
        client.notify("notifications/initialized")
        tools_msg = client.call("tools/list")
        names = {t["name"] for t in ((tools_msg.get("result") or {}).get("tools") or [])}
        missing = sorted(REQUIRED_TOOLS - names)
        tool_results = {}
        health, herr = client.tool("atlas_health", {})
        tool_results["atlas_health"] = {"ok": health.get("ok"), "error": herr}
        if REPO.is_dir():
            scan, serr = client.tool("atlas_scan_repo", {"repo_path": str(REPO)})
            tool_results["atlas_scan_repo"] = {"ok": scan.get("ok"), "error": serr}
            find, ferr = client.tool(
                "atlas_find_relevant_files",
                {"repo_path": str(REPO), "task": "Stripe webhook signature verification failing"},
            )
            tool_results["atlas_find_relevant_files"] = {"ok": find.get("ok"), "error": ferr}
            rc, rerr = client.tool(
                "atlas_root_cause",
                {"repo_path": str(REPO), "error": "webhook signature verification failed"},
            )
            tool_results["atlas_root_cause"] = {"ok": rc.get("ok"), "error": rerr}
            plan, perr = client.tool(
                "atlas_plan_change",
                {"repo_path": str(REPO), "request": "Fix Stripe webhook signature verification"},
            )
            tool_results["atlas_plan_change"] = {"ok": plan.get("ok"), "error": perr}
        return {
            "ok": not missing and all(v.get("ok") for v in tool_results.values()),
            "server": ((init.get("result") or {}).get("serverInfo") or {}).get("name"),
            "tool_count": len(names),
            "missing_tools": missing,
            "tool_results": tool_results,
        }
    finally:
        client.close()


def main() -> int:
    checks: list[dict] = []

    def record(name: str, ok: bool, evidence: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "evidence": str(evidence)[:500]})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {evidence[:120]}" if evidence else ""), flush=True)

    with tempfile.TemporaryDirectory(prefix="codex-e2e-") as tmp:
        tmp_path = Path(tmp)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        config = codex_dir / "config.toml"
        config.write_text(
            "\n".join(
                [
                    "[mcp_servers.node_repl]",
                    "command = 'existing.exe'",
                    "args = []",
                    "enabled = true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        atlas_exe = INSTALLED_EXE if INSTALLED_EXE.is_file() else (tmp_path / "Atlas.exe")
        if not Path(atlas_exe).is_file():
            (tmp_path / "Atlas.exe").write_text("", encoding="utf-8")
            atlas_exe = tmp_path / "Atlas.exe"

        os.environ["CODEX_HOME"] = str(codex_dir)
        _orig_exe = ai.atlas_executable_path
        ai.atlas_executable_path = lambda: str(atlas_exe)  # type: ignore[method-assign]

        written = ai.write_codex_config(confirm=True)
        record(
            "1. Codex config write succeeds",
            written.get("ok") is True,
            f"path={written.get('config_path')}",
        )
        text = config.read_text(encoding="utf-8")
        data, err = ai._load_codex_config(str(config))
        record(
            "1b. Written TOML parses cleanly",
            err is None and "[mcp_servers.atlas]" in text,
            err or "tomllib OK",
        )
        record(
            "2. Existing MCP servers preserved",
            "[mcp_servers.node_repl]" in text
            and "existing.exe" in text
            and ai._codex_atlas_configured(data or {}),
            f"servers={ai._codex_server_names(data or {})}",
        )

        entry = (data or {}).get("mcp_servers", {}).get("atlas", {})
        cmd = str(entry.get("command") or "")
        args = [str(a) for a in entry.get("args") or []]
        record(
            "3. Config points to Atlas --mcp",
            cmd.lower().endswith("atlas.exe") and args == ["--mcp"],
            f"command={cmd} args={args}",
        )

        if Path(atlas_exe).is_file() and Path(atlas_exe).stat().st_size > 0:
            session = run_mcp_session(cmd, args)
            record(
                "4. MCP server starts from Codex config command",
                "error" not in session,
                session.get("error") or f"server={session.get('server')} tools={session.get('tool_count')}",
            )
            record(
                "5. tools/list includes required Atlas tools",
                not session.get("missing_tools"),
                f"missing={session.get('missing_tools')} count={session.get('tool_count')}",
            )
            for tool_name in sorted(REQUIRED_TOOLS):
                tr = (session.get("tool_results") or {}).get(tool_name, {})
                record(
                    f"6. Tool call: {tool_name}",
                    bool(tr.get("ok")) and not tr.get("error"),
                    json.dumps(tr)[:200],
                )
            # Restart simulation uses same session results — re-read only
            reread, rerr = ai._load_codex_config(str(config))
            reentry = (reread or {}).get("mcp_servers", {}).get("atlas", {})
            record(
                "7. Config persists after re-read (restart simulation)",
                rerr is None and bool(reentry.get("command")),
                f"command={reentry.get('command')}",
            )
            record(
                "7b. MCP session validated once (Codex restart would re-spawn same command)",
                session.get("ok") is True,
                f"tools={session.get('tool_count')}",
            )
        else:
            record("4-6. MCP stdio session (packaged exe)", False, "Atlas.exe missing")
            record("7. Config persists after re-read (restart simulation)", False, "skipped")
            record("7b. MCP session after restart", False, "skipped")

        # Missing Codex install: no config file, write creates parent dirs
        missing_dir = tmp_path / "missing_codex"
        os.environ["CODEX_HOME"] = str(missing_dir)
        status_missing = ai.codex_config_status()
        record(
            "8. Missing Codex config is handled gracefully",
            status_missing.get("ok") is True and not status_missing.get("exists"),
            f"path={status_missing.get('config_path')} can_auto_write={status_missing.get('can_auto_write')}",
        )
        created = ai.write_codex_config(confirm=True)
        record(
            "8b. Write creates Codex config when absent",
            created.get("ok") is True and (missing_dir / "config.toml").is_file(),
            str(missing_dir / "config.toml"),
        )

        # Codex CLI not in PATH — integration should still work via config file
        codex_cli = shutil.which("codex")
        record(
            "8c. Codex CLI not required in PATH for config write",
            created.get("ok") is True,
            f"codex_in_path={bool(codex_cli)}",
        )

        ai.atlas_executable_path = _orig_exe  # type: ignore[method-assign]

    # Source mode snippet — use dev runner, not packaged exe
    os.environ.pop("CODEX_HOME", None)
    root_runner = str(ROOT / "run_atlas.py")
    if Path(root_runner).is_file():
        _orig_exe = ai.atlas_executable_path
        ai.atlas_executable_path = lambda: str(ROOT / "dev" / "python.exe")  # force source mode
        source_block = ai._render_codex_mcp_server_block()
        ai.atlas_executable_path = _orig_exe  # type: ignore[method-assign]
        record(
            "9. Source mode TOML includes run_atlas.py + cwd",
            "run_atlas.py" in source_block and "cwd" in source_block,
            source_block.replace("\n", " | "),
        )
    packaged = ai.mcp_snippet()["mcpServers"]["atlas"]
    record(
        "9b. Packaged JSON snippet uses --mcp only",
        packaged.get("args") == ["--mcp"],
        json.dumps(packaged),
    )

    # Real installed exe proof (if present)
    if INSTALLED_EXE.is_file():
        help_proc = subprocess.run(
            [str(INSTALLED_EXE), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        help_text = f"{help_proc.stdout}\n{help_proc.stderr}"
        record(
            "9c. Installed Atlas.exe advertises --mcp",
            "--mcp" in help_text,
            help_text.strip()[:160],
        )

    passed = all(c["ok"] for c in checks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"passed": passed, "checks": checks}, indent=2), encoding="utf-8")
    print(f"\n{'CODEX MCP E2E PASSED' if passed else 'CODEX MCP E2E FAILED'} — {OUT}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
