"""v1.0.5 Ask quality benchmark — 30+ realistic questions across four repos.

Runs the deterministic local Ask engine against:
  - Atlas Demo — Medium (bundled pack)
  - a real Python repository (path via ATLAS_BENCH_REAL_REPO; results aggregated,
    no private paths recorded)
  - a generated JavaScript/TypeScript fixture
  - the two isolation fixtures (repo A / repo B) with cross-leak checks

Records per question: route mode, ok, grounded (evidence or files present),
confidence, duration. Writes JSON next to this file; the release benchmark doc
summarizes it.

Usage:
    python benchmarks/ask_quality_benchmark.py [output.json]
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

os.environ.setdefault("ATLAS_TEST_MODE", "1")
if not os.environ.get("ATLAS_DESKTOP_DATA"):
    os.environ["ATLAS_DESKTOP_DATA"] = tempfile.mkdtemp(prefix="atlas-bench-")

from atlas_desktop import api  # noqa: E402

GENERIC_QUESTIONS = [
    "Where is authentication implemented?",
    "What is the most dangerous part of this repo?",
    "What part of the code has the biggest blast radius?",
    "Explain the request flow.",
    "Which files should I read first?",
    "Why is repository scanning slow?",
    "Prepare context for Cursor.",
    "What changed since my last scan?",
    "What does this repository do?",
    "What are the top architectural risks?",
    "Show import cycles",
    "Where should I start reading this codebase?",
    "How does the code handle errors?",
    "tell me about this repo",           # vague / broad
    "help",                              # vague
    "What braeks if I chnage the main module?",   # typos
    "Wich files depend on the entry point?",       # typo
    "explian the architechture",                   # typos
    "what",                              # incomplete
    "Can you make me a sandwich?",       # unsupported
    "Deploy this to production",         # unsupported
]

PER_REPO_QUESTIONS = {
    "demo_medium": [
        "What breaks if I change services/billing.py?",
        "Who imports services/billing.py?",
        "Where is billing handled?",
        "What tests cover the api subsystem?",
    ],
    "real_python": [],   # filled dynamically from the scan's own top hub
    "js_fixture": [
        "What breaks if I change lib/db.js?",
        "Who imports routes/auth.js?",
        "Where is authentication implemented?",
    ],
    "repo_a": ["Where is unique_a_symbol implemented?",
               "What breaks if I change only_a.py?"],
    "repo_b": ["Where is unique_b_symbol implemented?",
               "What breaks if I change only_b.py?"],
}

LEAK_TERMS = {
    "repo_a": ("only_b", "unique_b_symbol"),
    "repo_b": ("only_a", "unique_a_symbol"),
}


def _make_js_fixture(base: Path) -> str:
    r = base / "js_fixture"
    (r / "routes").mkdir(parents=True)
    (r / "lib").mkdir()
    (r / "tests").mkdir()
    (r / "lib" / "db.js").write_text(
        "export function query(sql) { return []; }\n", encoding="utf-8")
    (r / "routes" / "auth.js").write_text(
        "import { query } from '../lib/db.js';\n"
        "export function login(user) { return query('select 1'); }\n", encoding="utf-8")
    (r / "routes" / "users.js").write_text(
        "import { query } from '../lib/db.js';\n"
        "import { login } from './auth.js';\n"
        "export function listUsers() { return query('select *'); }\n", encoding="utf-8")
    (r / "server.js").write_text(
        "import { login } from './routes/auth.js';\n"
        "import { listUsers } from './routes/users.js';\n"
        "console.log('server');\n", encoding="utf-8")
    (r / "tests" / "auth.test.js").write_text(
        "import { login } from '../routes/auth.js';\n", encoding="utf-8")
    return str(r)


def _make_symbol_repo(base: Path, name: str, symbol_file: str, symbol: str) -> str:
    r = base / name
    r.mkdir(parents=True)
    (r / symbol_file).write_text(f"def {symbol}():\n    return '{name}'\n", encoding="utf-8")
    stem = symbol_file[:-3]
    for i in range(5):
        (r / f"user{i}.py").write_text(
            f"import {stem}\n\ndef caller():\n    return {stem}.{symbol}()\n",
            encoding="utf-8")
    return str(r)


def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


def run_repo(repo_key: str, questions: list) -> dict:
    rows = []
    for q in questions:
        t0 = time.time()
        try:
            res = api.copilot_ask(q)
        except Exception as exc:  # engine crash = automatic failure
            res = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "mode": "crash"}
        ms = round((time.time() - t0) * 1000)
        grounded = bool(res.get("ok")) and bool(res.get("evidence") or res.get("files"))
        blob = json.dumps(res, default=str).lower()
        leaked = any(term in blob for term in LEAK_TERMS.get(repo_key, ()))
        rows.append({
            "repo": repo_key,
            "question": q,
            "mode": res.get("mode", ""),
            "ok": bool(res.get("ok")),
            "grounded": grounded,
            "confidence": res.get("confidence", ""),
            "interpretations": len(res.get("interpretations") or []),
            "duration_ms": ms,
            "leaked": leaked,
        })
    return rows


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "ask_quality_results.json")
    all_rows = []
    base = Path(tempfile.mkdtemp(prefix="atlas-ask-bench-"))

    # 1) Demo medium
    _fresh_state()
    demo = api.load_demo_mode("medium")
    if demo.get("ok"):
        all_rows += run_repo("demo_medium",
                             GENERIC_QUESTIONS + PER_REPO_QUESTIONS["demo_medium"])
    else:
        print("WARN: demo medium unavailable:", demo.get("error"))

    # 2) Real Python repository (aggregate only)
    real = os.environ.get("ATLAS_BENCH_REAL_REPO", r"C:\FINAL_ALGO_TRADER - Copy")
    if os.path.isdir(real):
        _fresh_state()
        scan = api.scan_repository(real)
        if scan.get("ok"):
            hub = (scan.get("top_hubs") or [{}])[0].get("path") or ""
            qs = list(GENERIC_QUESTIONS)
            if hub:
                qs += [f"What breaks if I change {hub}?", f"Who imports {hub}?"]
            all_rows += run_repo("real_python", qs)

    # 3) JS fixture
    js = _make_js_fixture(base)
    _fresh_state()
    if api.scan_repository(js).get("ok"):
        all_rows += run_repo("js_fixture",
                             GENERIC_QUESTIONS[:8] + PER_REPO_QUESTIONS["js_fixture"])

    # 4) Isolation repos
    a = _make_symbol_repo(base, "repo_a", "only_a.py", "unique_a_symbol")
    b = _make_symbol_repo(base, "repo_b", "only_b.py", "unique_b_symbol")
    for key, path in (("repo_a", a), ("repo_b", b)):
        _fresh_state()
        if api.scan_repository(path).get("ok"):
            all_rows += run_repo(key, PER_REPO_QUESTIONS[key])

    total = len(all_rows)
    routed = sum(1 for r in all_rows if r["mode"] not in ("", "unknown", "crash"))
    grounded = sum(1 for r in all_rows if r["grounded"])
    failures = sum(1 for r in all_rows if not r["ok"] and r["mode"] == "crash")
    leaks = sum(1 for r in all_rows if r["leaked"])
    unknown_with_help = sum(
        1 for r in all_rows
        if r["mode"] == "unknown" and (r["interpretations"] or r["ok"]))
    durations = [r["duration_ms"] for r in all_rows]

    summary = {
        "total_questions": total,
        "routed_rate": round(routed / total, 3) if total else 0,
        "grounded_rate": round(grounded / total, 3) if total else 0,
        "crash_failure_rate": round(failures / total, 3) if total else 0,
        "cross_repo_leaks": leaks,
        "unknown_with_recovery": unknown_with_help,
        "median_ms": statistics.median(durations) if durations else 0,
        "p95_ms": (sorted(durations)[int(len(durations) * 0.95) - 1] if durations else 0),
    }
    payload = {"summary": summary, "rows": all_rows, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(json.dumps(summary, indent=2))
    print("rows written to", out_path)
    return 0 if leaks == 0 and failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
