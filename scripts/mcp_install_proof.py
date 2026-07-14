"""Installed-Atlas MCP proof: drive the FROZEN Atlas.exe --mcp over real stdio.

Unlike scripts/mcp_smoke_test.py (which spawns `python -m atlas_desktop.mcp_server`),
this exercises the packaged windowed exe's `--mcp` stdout-rebind path against a real
JSON-RPC-over-pipes client — the one piece that was previously unverified.

Usage:
  py -3 scripts/mcp_install_proof.py [path\\to\\Atlas.exe] [path\\to\\repo]
Defaults: dist/Atlas/Atlas.exe  +  builder_core/tests/fixtures/tiny_repo (if present)
Saves a transcript to reports/pre_beta_fix/mcp_proof/result.json and prints PASS/FAIL.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "Atlas", "Atlas.exe")
_SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs"}


def _contains_source_files(path):
    if not os.path.isdir(path):
        return False
    return any(
        os.path.splitext(filename)[1].lower() in _SOURCE_EXTENSIONS
        for _, _, filenames in os.walk(path)
        for filename in filenames
    )


REPO_CANDIDATES = [
    os.path.join(ROOT, "builder_core", "tests", "fixtures", "tiny_repo"),
    os.path.join(ROOT, "external_repos", "requests"),
    os.path.join(ROOT, "atlas_desktop", "demo", "medium_repo"),
    os.path.join(ROOT, "atlas_desktop", "demo", "small_repo"),
]
REPO = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else next(
    (p for p in REPO_CANDIDATES if _contains_source_files(p)),
    REPO_CANDIDATES[-1],
)
OUTDIR = os.path.join(ROOT, "reports", "pre_beta_fix", "mcp_proof")


def _isolated_child_env():
    """Return a fail-closed, disposable Atlas data root for every proof child."""
    data_root = tempfile.mkdtemp(prefix="atlas-mcp-install-proof-")
    user_home = os.environ.get("USERPROFILE", "").strip() or os.path.expanduser("~")
    protected_root = os.path.abspath(os.path.join(user_home, ".atlas_desktop"))
    if os.path.normcase(os.path.abspath(data_root)) == os.path.normcase(protected_root):
        raise RuntimeError("MCP install proof refused the canonical Atlas data root")
    env = dict(os.environ)
    env.update(
        {
            "ATLAS_TEST_MODE": "1",
            "ATLAS_TEST_PROTECTED_DATA_ROOT": protected_root,
            "ATLAS_DESKTOP_DATA": data_root,
            "JARVIS_DESKTOP_DATA": data_root,
        }
    )
    return env, data_root


class Client:
    def __init__(self, proc):
        self.proc = proc
        self._id = 0

    def _send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def call(self, method, params=None, timeout=60):
        self._id += 1
        mid = self._id
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                return {"error": "eof"}
            line = line.decode("utf-8", "replace").strip()
            if not line or not line.startswith("{"):
                continue
            msg = json.loads(line)
            if msg.get("id") == mid:
                return msg
        return {"error": "timeout"}

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})


def tool(client, name, args):
    r = client.call("tools/call", {"name": name, "arguments": args})
    content = (((r.get("result") or {}).get("content") or [{}])[0]).get("text") or "{}"
    try:
        return json.loads(content), r.get("result", {}).get("isError", False)
    except Exception:
        return {"raw": content}, True


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    checks, transcript = [], {}

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("Atlas.exe exists", os.path.isfile(EXE), EXE)
    if not os.path.isfile(EXE):
        print("ABORT: build the installer first (packaging/installer/installer_build.ps1).")
        json.dump({"checks": checks}, open(os.path.join(OUTDIR, "result.json"), "w"), indent=2)
        return 2

    child_env, data_root = _isolated_child_env()

    try:
        help_proc = subprocess.run(
            [EXE, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=child_env,
        )
        help_text = f"{help_proc.stdout or ''}\n{help_proc.stderr or ''}"
        check(
            "Atlas.exe --help lists --mcp",
            "--mcp" in help_text and "unrecognized arguments" not in help_text.lower(),
            help_text.strip()[:160],
        )
    except Exception as e:
        check("Atlas.exe --help runs", False, f"{type(e).__name__}: {e}")

    try:
        rc = subprocess.run([EXE, "--self-test"], timeout=120, env=child_env).returncode
        check("Atlas.exe --self-test exit 0 (ready)", rc == 0, f"exit={rc}")
    except Exception as e:
        check("Atlas.exe --self-test runs", False, f"{type(e).__name__}: {e}")

    proc = subprocess.Popen(
        [EXE, "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env,
    )
    try:
        time.sleep(0.5)
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
            check("Atlas.exe --mcp starts (no argparse error)", "unrecognized arguments" not in err.lower(), err[:200])
            raise SystemExit(1)

        check("Atlas.exe --mcp starts (no argparse error)", True, "process alive")
        client = Client(proc)
        init = client.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "install-proof", "version": "0"},
            },
        )
        sname = str(((init.get("result") or {}).get("serverInfo") or {}).get("name", ""))
        check("initialize returns serverInfo", sname.startswith("atlas"), sname or str(init)[:120])
        transcript["initialize"] = init.get("result")
        client.notify("notifications/initialized")

        tl = client.call("tools/list")
        names = [t["name"] for t in ((tl.get("result") or {}).get("tools") or [])]
        primary_tools = {
            "atlas_scan_repo",
            "atlas_get_codebase_map",
            "atlas_build_context_pack",
            "atlas_what_breaks",
            "atlas_plan_change",
            "atlas_find_file",
            "atlas_repo_health",
        }
        check(
            "tools/list returns all seven primary Atlas tools",
            primary_tools.issubset(set(names)),
            f"{len(names)} tools",
        )
        transcript["tools"] = names

        h, herr = tool(client, "atlas_health", {})
        check("atlas_health works (no error, no secret leak)", h.get("ok") and not herr, json.dumps(h)[:160])
        transcript["atlas_health"] = h

        if os.path.isdir(REPO):
            s, serr = tool(client, "atlas_scan_repo", {"repo_path": REPO})
            check(
                "atlas_scan_repo works on demo repo",
                s.get("ok") and not serr,
                f"files={((s.get('scan') or {}).get('file_count'))}",
            )
            transcript["atlas_scan_repo"] = {"ok": s.get("ok"), "scan": s.get("scan")}

            repo_name = os.path.basename(REPO)
            if repo_name == "requests":
                task = "add retry with exponential backoff to the HTTP adapter"
                probe_query, probe_target = "session cookie handling", "src/requests/sessions.py"
            else:
                task = "add authentication checks to API request handlers"
                probe_query, probe_target = "api request handlers", "api/handlers.py"

            tool_calls = [
                ("atlas_get_codebase_map", {"limit": 8}),
                (
                    "atlas_build_context_pack",
                    {"task": task, "max_files": 8},
                ),
                ("atlas_what_breaks", {"target": probe_target}),
                (
                    "atlas_plan_change",
                    {"request": task},
                ),
                ("atlas_find_file", {"query": probe_query, "limit": 5}),
                ("atlas_repo_health", {}),
            ]
            for name, arguments in tool_calls:
                payload, is_error = tool(client, name, arguments)
                check(f"{name} works", payload.get("ok") is True and not is_error, json.dumps(payload)[:160])
                transcript[name] = payload
    finally:
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(data_root, ignore_errors=True)

    passed = all(c["ok"] for c in checks)
    json.dump(
        {"exe": EXE, "repo": REPO, "passed": passed, "checks": checks, "transcript": transcript},
        open(os.path.join(OUTDIR, "result.json"), "w"),
        indent=2,
    )
    print(("\nINSTALL-MCP PROOF PASSED" if passed else "\nINSTALL-MCP PROOF FAILED") + f" — saved {OUTDIR}/result.json")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
