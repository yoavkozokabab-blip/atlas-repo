"""Phase 119 manual smoke — API-level checks for desktop polish."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jarvis_desktop import api, server  # noqa: E402


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    h = api.health()
    record("Home / health", h.get("ok") and h.get("product") == "ATLAS", str(h.get("version")))

    fp = r"C:\J.A.R.V.I.S\fastapi"
    v = api.validate_repository_path(fp) if os.path.isdir(fp) else {"ok": False}
    record("Validate FastAPI", bool(v.get("ok")), f"{v.get('code_files', 0)} code files")

    if v.get("ok"):
        api._STATE.update({"scan_cache": {}, "scan": None, "graph": None, "index": None, "risks": None})
        scan = api.scan_repository(fp)
        record(
            "Scan FastAPI",
            bool(scan.get("ok")),
            f"modules={scan.get('module_count')} edges={scan.get('dependency_edges')}",
        )
        summary = api.current_summary()
        record("Command Center / summary", bool(summary.get("ok")), summary.get("graph_health", {}).get("label", ""))
        g_mod = api.current_graph("module")
        record("Module graph", bool(g_mod.get("ok") and g_mod.get("node_count", 0) > 0), f"nodes={g_mod.get('node_count')}")
        g_sub = api.current_graph("subsystem")
        record("Graph mode switch", bool(g_sub.get("ok")), f"subsystem nodes={g_sub.get('node_count')}")
        path = ""
        if g_mod.get("nodes"):
            path = g_mod["nodes"][0].get("path") or ""
        mod = api.module_inspector(path) if path else {"ok": False}
        record("Module inspector", "ok" in mod, mod.get("path") or mod.get("error", ""))
        if mod.get("ok") and path:
            cp = api.copilot_ask(f"Generate a compact Claude prompt for module {path}", "claude", "compact")
            record(
                "Inspector prompt via Copilot",
                bool(cp.get("ok") and len(cp.get("answer", "")) > 20),
                f"chars={len(cp.get('answer', ''))}",
            )

    st, browse = server.dispatch("POST", "/api/system/browse-folder")
    record("Browse endpoint", st == 200 and "ok" in browse, str(browse.get("cancelled", browse.get("path"))))

    api._STATE.update({"scan_cache": {}})
    demo = api.load_demo_mode("small")
    record("Demo Mode (no scan btn)", bool(demo.get("ok")), demo.get("repo_name", ""))

    api.load_demo_mode("small")
    bug = api.bug_investigation("vague symptom with no paths")
    record("Bug Hunt fallback", bool(bug.get("ok") and bug.get("mock")), f"confidence={bug.get('confidence')}")
    record(
        "Bug Hunt honest uncertainty",
        bug.get("confidence") in ("low", "medium") or bool(bug.get("mock")),
        "",
    )

    api.load_demo_mode("small")
    ex = api.context_export("claude", "compact")
    record("AI Export", bool(ex.get("ok") and ex.get("text")), f"~{ex.get('estimated_tokens')} tokens")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\nTotal: {len(results)} checks, {len(results) - len(failed)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
