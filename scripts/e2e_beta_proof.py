"""End-to-end MCP value-moment proof: drive the FROZEN Atlas.exe --mcp exactly as
Claude Desktop would, for the question "Where is authentication implemented?".

Captures every tool call, MCP response, and per-step timing. This is the real
transport/value proof (the MCP client role Claude plays); it does NOT and cannot
stand in for the Claude Desktop UI or Claude's natural-language answer.

Usage: py -3 scripts/e2e_beta_proof.py [Atlas.exe] [repo]
Defaults: dist/Atlas/Atlas.exe + external_repos/requests
Writes reports/end_to_end_proof/mcp_transcript.json
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "Atlas", "Atlas.exe")
REPO = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(ROOT, "external_repos", "requests")
OUT = os.path.join(ROOT, "reports", "end_to_end_proof")
QUESTION = "Where is authentication implemented?"


class Client:
    def __init__(self, proc):
        self.proc = proc
        self._id = 0

    def _send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + "\n").encode()); self.proc.stdin.flush()

    def rpc(self, method, params=None, timeout=120):
        self._id += 1; mid = self._id
        t0 = time.time()
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                return {"error": "eof"}, round((time.time() - t0) * 1000)
            s = line.decode("utf-8", "replace").strip()
            if s.startswith("{"):
                m = json.loads(s)
                if m.get("id") == mid:
                    return m, round((time.time() - t0) * 1000)
        return {"error": "timeout"}, round((time.time() - t0) * 1000)

    def notify(self, method):
        self._send({"jsonrpc": "2.0", "method": method, "params": {}})


def tool_payload(resp):
    txt = (((resp.get("result") or {}).get("content") or [{}])[0]).get("text") or "{}"
    try:
        return json.loads(txt)
    except Exception:
        return {"raw": txt[:400]}


def main():
    os.makedirs(OUT, exist_ok=True)
    steps = []

    def log(name, ms, summary, payload=None):
        steps.append({"step": name, "ms": ms, "summary": summary})
        print(f"  [{ms:>6} ms] {name}: {summary}")
        return payload

    proc = subprocess.Popen([EXE, "--mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    transcript = {"exe": EXE, "repo": REPO, "question": QUESTION, "steps": steps, "calls": {}}
    t_start = time.time()
    client = Client(proc)
    try:
        r, ms = client.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                          "clientInfo": {"name": "e2e-proof", "version": "0"}})
        log("initialize", ms, "serverInfo=" + str((r.get("result") or {}).get("serverInfo")))
        client.notify("notifications/initialized")

        r, ms = client.rpc("tools/list")
        names = [t["name"] for t in (r.get("result") or {}).get("tools", [])]
        transcript["calls"]["tools_list"] = names
        log("tools/list (tools Claude would see)", ms, f"{len(names)} tools: {', '.join(names[:6])}…")

        r, ms = client.rpc("tools/call", {"name": "atlas_health", "arguments": {}})
        h = tool_payload(r); transcript["calls"]["atlas_health"] = h
        log("tools/call atlas_health", ms, f"ok={h.get('ok')} version={h.get('mcp_version')}")

        r, ms = client.rpc("tools/call", {"name": "atlas_scan_repo", "arguments": {"repo_path": REPO}})
        s = tool_payload(r); transcript["calls"]["atlas_scan_repo"] = {"ok": s.get("ok"), "scan": s.get("scan")}
        log("tools/call atlas_scan_repo", ms, f"ok={s.get('ok')} files={(s.get('scan') or {}).get('file_count')}")

        # THE QUESTION — exactly what Claude would call for "where is auth implemented?"
        r, ms = client.rpc("tools/call", {"name": "atlas_find_relevant_files", "arguments": {"task": QUESTION}})
        f = tool_payload(r); transcript["calls"]["atlas_find_relevant_files"] = f
        files = [x.get("path") for x in (f.get("recommended_files") or [])][:6]
        log("tools/call atlas_find_relevant_files", ms, f"conf={f.get('confidence')} files={files}")

        r, ms = client.rpc("tools/call", {"name": "atlas_build_context_pack", "arguments": {"task": QUESTION}})
        p = tool_payload(r); transcript["calls"]["atlas_build_context_pack"] = p
        recs = [(x.get("path"), x.get("relevance_score")) for x in (p.get("recommended_files") or [])][:6]
        log("tools/call atlas_build_context_pack", ms,
            f"conf={p.get('confidence')} tokens={p.get('token_estimate')} top={recs}")
    finally:
        try:
            proc.stdin.close(); proc.terminate()
        except Exception:
            pass

    transcript["total_ms"] = round((time.time() - t_start) * 1000)
    json.dump(transcript, open(os.path.join(OUT, "mcp_transcript.json"), "w"), indent=2)
    print(f"\nTotal MCP journey: {transcript['total_ms']} ms — saved {OUT}/mcp_transcript.json")


if __name__ == "__main__":
    raise SystemExit(main())
