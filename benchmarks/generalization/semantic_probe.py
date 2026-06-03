"""Phase 136 — semantic generalization probe (measurement only).

Probes a fixed taxonomy of 20 cross-cutting software concepts against every
available repository through the REAL user-facing impact route
(``api.copilot_ask`` → semantic resolver → impact engine) and records, per
concept, whether Atlas resolved it to real modules or fell back. This is the
evidence base for the Semantic Generalization Roadmap. Atlas is never modified.

Output: ``results/semantic/<repo>.json`` (+ ``aggregate.json``).

Usage:
    py -3 benchmarks/generalization/semantic_probe.py                 # all available
    py -3 benchmarks/generalization/semantic_probe.py fastapi django
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.generalization import registry  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "results" / "semantic"

# 20 canonical cross-cutting concepts. Each: id, the natural-language phrase fed
# to the impact route ("what breaks if I remove <phrase>"), and the subsystem a
# correct resolver should land in (used as the 'expected subsystem' column).
CONCEPTS: List[Dict[str, str]] = [
    {"id": "authentication", "phrase": "authentication", "subsystem": "auth / identity"},
    {"id": "authorization", "phrase": "authorization", "subsystem": "access control / permissions"},
    {"id": "caching", "phrase": "caching", "subsystem": "cache layer"},
    {"id": "configuration", "phrase": "configuration", "subsystem": "config system"},
    {"id": "database", "phrase": "the database layer", "subsystem": "persistence / database"},
    {"id": "routing", "phrase": "routing", "subsystem": "router / URL dispatch"},
    {"id": "middleware", "phrase": "middleware", "subsystem": "middleware pipeline"},
    {"id": "logging", "phrase": "the logging layer", "subsystem": "logging subsystem"},
    {"id": "events", "phrase": "the event system", "subsystem": "event bus / dispatcher"},
    {"id": "messaging", "phrase": "messaging", "subsystem": "message queue / pub-sub"},
    {"id": "background_jobs", "phrase": "background jobs", "subsystem": "task / worker queue"},
    {"id": "scheduling", "phrase": "scheduling", "subsystem": "scheduler"},
    {"id": "state_management", "phrase": "state management", "subsystem": "state store"},
    {"id": "plugins", "phrase": "the plugin system", "subsystem": "plugin loader"},
    {"id": "extensions", "phrase": "extensions", "subsystem": "extension system"},
    {"id": "websockets", "phrase": "websocket support", "subsystem": "websocket transport"},
    {"id": "api_layer", "phrase": "the api layer", "subsystem": "API / endpoint layer"},
    {"id": "persistence", "phrase": "persistence", "subsystem": "ORM / storage"},
    {"id": "validation", "phrase": "request validation", "subsystem": "input validation"},
    {"id": "serialization", "phrase": "serialization", "subsystem": "(de)serialization layer"},
]

_PROMPT = "what breaks if I remove {phrase}"


def _reset_state() -> None:
    from jarvis_desktop import api
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "architecture": None,
                       "scan_cache": {}})


def _classify(resp: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(resp.get("answer", ""))
    low = answer.lower()
    is_fallback = ("Name a file" in answer) or ("could not be resolved" in low) \
        or ("not in the production graph" in low)
    modules = (resp.get("resolved_modules") or resp.get("direct_impact")
               or resp.get("indirect_impact") or resp.get("files") or [])
    has_modules = bool(modules)
    resolved = (not is_fallback) and has_modules
    if resolved:
        category = None
    elif is_fallback:
        category = "semantic_routing_failure"
    else:
        category = "resolver_failure"
    return {
        "resolved": resolved,
        "category": category,
        "label": resp.get("semantic_label"),
        "modules": list(modules)[:3],
        "confidence": resp.get("confidence"),
        "actual": ("fallback — no target" if is_fallback else
                   ("resolved → " + ", ".join(str(m) for m in list(modules)[:3]))
                   if has_modules else "empty impact (no modules)"),
    }


def probe_repo(resolved: "registry.ResolvedRepo") -> Dict[str, Any]:
    from jarvis_desktop import api
    spec = resolved.spec
    rec: Dict[str, Any] = {"id": spec.id, "display": spec.display, "language": spec.language,
                           "available": resolved.available,
                           "path": str(resolved.path) if resolved.path else None}
    if not resolved.available:
        rec.update({"status": "unavailable", "concepts": []})
        return rec
    _reset_state()
    t0 = time.time()
    try:
        scan = api.scan_repository(str(resolved.path))
    except Exception as exc:
        rec.update({"status": "scan_crash", "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()[-1200:], "concepts": []})
        return rec
    if not scan.get("ok"):
        rec.update({"status": "scan_failed", "error": scan.get("error"), "concepts": []})
        return rec
    rec["modules"] = scan.get("module_count")
    out = []
    for c in CONCEPTS:
        prompt = _PROMPT.format(phrase=c["phrase"])
        try:
            resp = api.copilot_ask(prompt, "none", "compact")
        except Exception as exc:
            resp = {"answer": f"crash: {exc}"}
        cls = _classify(resp)
        out.append({"concept": c["id"], "phrase": c["phrase"], "expected_subsystem": c["subsystem"],
                    "prompt": prompt, **cls})
    rec["concepts"] = out
    rec["status"] = "ok"
    rec["resolved_count"] = sum(1 for o in out if o["resolved"])
    rec["scan_seconds"] = round(time.time() - t0, 1)
    return rec


def run(only: Optional[List[str]] = None) -> Dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = registry.available_repos()
    if only:
        wanted = set(only)
        repos = [r for r in repos if r.spec.id in wanted]
    results = []
    for resolved in repos:
        if not resolved.available:
            continue  # skip unavailable here; the main benchmark already records them
        print(f"[semantic] {resolved.spec.id} probing {len(CONCEPTS)} concepts ...", flush=True)
        rec = probe_repo(resolved)
        results.append(rec)
        (OUT_DIR / f"{resolved.spec.id}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(f"[semantic] {resolved.spec.id} status={rec.get('status')} "
              f"resolved={rec.get('resolved_count')}/{len(CONCEPTS)}", flush=True)
    agg = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "concepts": [c["id"] for c in CONCEPTS],
           "results": results}
    (OUT_DIR / "aggregate.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    return agg


if __name__ == "__main__":
    run(sys.argv[1:] or None)
