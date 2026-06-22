"""Installed-Atlas MCP proof: drive the FROZEN Atlas.exe --mcp over real stdio.

Unlike scripts/mcp_smoke_test.py (which spawns `python -m jarvis_desktop.mcp_server`),
this exercises the packaged windowed exe's `--mcp` stdout-rebind path against a real
JSON-RPC-over-pipes client — the one piece that was previously unverified.

Usage:
  py -3 scripts/mcp_install_proof.py [path\\to\\Atlas.exe] [path\\to\\repo]
Defaults: dist/Atlas/Atlas.exe  +  external_repos/requests
Saves a transcript to reports/pre_beta_fix/mcp_proof/result.json and prints PASS/FAIL.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "Atlas", "Atlas.exe")
REPO = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(ROOT, "external_repos", "requests")
OUTDIR = os.path.join(ROOT, "reports", "pre_beta_fix", "mcp_proof")


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

    # 1) self-test (writes self_test.json in the data dir; exit 0 = ready)
    try:
        rc = subprocess.run([EXE, "--self-test"], timeout=120).returncode
        check("Atlas.exe --self-test exit 0 (ready)", rc == 0, f"exit={rc}")
    except Exception as e:
        check("Atlas.exe --self-test runs", False, f"{type(e).__name__}: {e}")

    # 2) --mcp over stdio (the previously-unverified frozen path)
    proc = subprocess.Popen([EXE, "--mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    try:
        client = Client(proc)
        init = client.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                           "clientInfo": {"name": "install-proof", "version": "0"}})
        sname = str(((init.get("result") or {}).get("serverInfo") or {}).get("name", ""))
        check("initialize returns serverInfo", sname.startswith("atlas"), sname or str(init)[:120])
        transcript["initialize"] = init.get("result")
        client.notify("notifications/initialized")

        tl = client.call("tools/list")
        names = [t["name"] for t in ((tl.get("result") or {}).get("tools") or [])]
        check("tools/list returns Atlas tools", any(n.startswith("atlas_") for n in names), f"{len(names)} tools")
        transcript["tools"] = names

        h, herr = tool(client, "atlas_health", {})
        check("atlas_health works (no error, no secret leak)", h.get("ok") and not herr, json.dumps(h)[:160])
        transcript["atlas_health"] = h

        s, serr = tool(client, "atlas_scan_repo", {"repo_path": REPO})
        check("atlas_scan_repo works on demo repo", s.get("ok") and not serr, f"files={((s.get('scan') or {}).get('file_count'))}")
        transcript["atlas_scan_repo"] = {"ok": s.get("ok"), "scan": s.get("scan")}

        rs, rerr = tool(client, "atlas_repo_summary", {})
        check("atlas_repo_summary works", rs.get("ok") and not rerr, f"name={rs.get('repo_name')}")
        transcript["atlas_repo_summary"] = {"ok": rs.get("ok"), "repo_name": rs.get("repo_name")}
    finally:
        try:
            proc.stdin.close(); proc.terminate()
        except Exception:
            pass

    passed = all(c["ok"] for c in checks)
    json.dump({"exe": EXE, "repo": REPO, "passed": passed, "checks": checks, "transcript": transcript},
              open(os.path.join(OUTDIR, "result.json"), "w"), indent=2)
    print(("\nINSTALL-MCP PROOF PASSED" if passed else "\nINSTALL-MCP PROOF FAILED") + f" — saved {OUTDIR}/result.json")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
