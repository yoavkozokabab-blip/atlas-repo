"""
Benchmark: current Atlas ranking vs a production-aware re-rank.

Drives the REAL ranker (jarvis_desktop.context_pack.build_context_pack_from_state)
on the actual jarvis_desktop scan, across 20 maintenance tasks whose gold files are
this repo's PRODUCTION modules. Then re-ranks the SAME candidate set with a
directory-ownership penalty (demo / external_repos / staging / packaging / build
artifacts) and remeasures. No engine code is modified — the production-aware step
is pure post-processing so the comparison is apples-to-apples.

Run: py -3 scripts/bench_production_aware_ranking.py
"""
from __future__ import annotations
import json, os, sys

REPO = r"C:\J.A.R.V.I.S\local_jarvis"
SCAN_TARGET = os.path.join(REPO, "jarvis_desktop")
sys.path.insert(0, REPO)

from jarvis_desktop import api, context_pack as cp  # noqa: E402
try:
    from jarvis_desktop import repository_memory as repo_memory  # noqa: E402
except Exception:
    repo_memory = None

# (task, [acceptable gold production files]) — gold = where the real work lives.
TASKS = [
    ("remove beta approval completely",              ["accounts_routes.py", "accounts_client.py"]),
    ("desktop authenticates against the website login", ["accounts_client.py"]),
    ("list the MCP tools the server exposes",        ["mcp_server/runtime.py"]),
    ("rank task-relevant files for a context pack",  ["context_pack.py"]),
    ("analyze root cause from a python stack trace", ["root_cause.py"]),
    ("reduce context tokens with symbol slicing",    ["context_pack.py"]),
    ("write the Cursor MCP configuration file",      ["agent_integrations.py"]),
    ("discover the Claude Desktop config path",      ["agent_integrations.py"]),
    ("repository memory freshness and drift refusal",["repository_memory.py"]),
    ("desktop HTTP API endpoints",                   ["api.py"]),
    ("usage limits and quota enforcement",           ["usage/limits.py", "usage/store.py"]),
    ("billing plan definitions",                     ["billing/plans.py"]),
    ("evidence engine symbol index",                 ["evidence_engine/symbol_index.py"]),
    ("architecture analyzer clusters",               ["architecture/analyzer.py"]),
    ("impact analysis what breaks",                  ["impact_engine/engine.py"]),
    ("first impression implementation status",       ["first_impression.py"]),
    ("desktop data directory resolution",            ["data_paths.py"]),
    ("evidence builder assembles evidence",          ["evidence_engine/evidence_builder.py"]),
    ("account device limit and removal",             ["accounts_routes.py", "accounts_client.py"]),
    ("install support and launcher log",             ["install_support.py"]),
]


def norm(p: str) -> str:
    return p.replace("\\", "/").lower()


def ownership_penalty(path: str) -> int:
    """Production-aware penalty. Positive = demote. Generic (not Atlas-specific)."""
    p = norm(path)
    parts = p.split("/")
    if "external_repos" in parts:
        return 1000  # vendored third-party: never a maintenance target for our code
    if any(x in parts for x in ("demo", "sample_repo", "small_repo", "medium_repo",
                                 "large_repo", "ts_sample_repo", "examples", "example",
                                 "samples", "fixtures")):
        return 60
    if any(x in parts for x in ("staging", "packaging", "_internal")) or \
       p.startswith("dist/") or "/dist/" in p or p.startswith("build/") or "/build/" in p or \
       any(seg.startswith(".phase") for seg in parts):
        return 60
    return 0


def build_state():
    res = api.scan_repository(SCAN_TARGET)
    if not res.get("ok"):
        print("scan failed:", res); sys.exit(1)
    state = dict(api._STATE)
    mem = api._STATE.get("repository_memory") or api._STATE.get("_current_memory")
    if not mem and repo_memory is not None:
        try:
            mem = repo_memory.build_memory(dict(api._STATE), generated_by_version="bench")
        except Exception:
            mem = {}
    return state, (mem or {})


def candidates_for(task, state, mem):
    """Return [(path, score)] from recommended + excluded (full scored set)."""
    pack = cp.build_context_pack_from_state(
        SCAN_TARGET, task, dict(state), memory=mem, include_snippets=False, max_files=24,
    )
    out = {}
    detail = {}
    for item in pack.get("recommended_files") or []:
        sc = float(item.get("score") or item.get("relevance_score") or 0)
        out[norm(item["path"])] = sc
        detail[norm(item["path"])] = {
            "score": sc,
            "reasons": item.get("reasons") or [],
            "matched_symbols": bool(item.get("matched_symbols")),
            "role": item.get("role"),
        }
    for item in pack.get("excluded_files") or []:
        np = norm(item["path"])
        if np not in out:
            out[np] = float(item.get("score") or 0)
            detail[np] = {"score": out[np], "reasons": [item.get("reason")], "matched_symbols": False, "role": None}
    return out, detail, pack


def ranked(scores, penalty=False):
    items = [(p, s - (ownership_penalty(p) if penalty else 0)) for p, s in scores.items()]
    items.sort(key=lambda x: (-x[1], x[0]))
    return [p for p, _ in items]


def hit_at(rank, gold, k):
    return 1 if any(g in rank[:k] for g in gold) else 0


def recall_at5(rank, gold):
    top = set(rank[:5])
    return len([g for g in gold if g in top]) / len(gold)


def main():
    state, mem = build_state()
    _files = (state.get("index") or {}).get("files") or []
    all_paths = {norm(f["path"] if isinstance(f, dict) else f) for f in _files}
    agg = {"cur": {"h1": 0, "h3": 0, "h5": 0, "rec": 0.0}, "prod": {"h1": 0, "h3": 0, "h5": 0, "rec": 0.0}}
    sym_hits = 0
    rows = []
    valid = 0
    headline = None
    for task, gold_raw in TASKS:
        gold = [norm(g) for g in gold_raw if norm(g) in all_paths]
        if not gold:
            rows.append((task, "GOLD MISSING", gold_raw)); continue
        valid += 1
        scores, detail, pack = candidates_for(task, state, mem)
        cur = ranked(scores, penalty=False)
        prod = ranked(scores, penalty=True)
        for arm, rk in (("cur", cur), ("prod", prod)):
            agg[arm]["h1"] += hit_at(rk, gold, 1)
            agg[arm]["h3"] += hit_at(rk, gold, 3)
            agg[arm]["h5"] += hit_at(rk, gold, 5)
            agg[arm]["rec"] += recall_at5(rk, gold)
        sym_hits += 1 if any(detail.get(g, {}).get("matched_symbols") for g in gold) else 0
        cur_top = cur[0] if cur else "-"
        prod_top = prod[0] if prod else "-"
        gold_rank_cur = min([cur.index(g) + 1 for g in gold if g in cur] or [0])
        gold_rank_prod = min([prod.index(g) + 1 for g in gold if g in prod] or [0])
        rows.append((task, f"cur#{gold_rank_cur} prod#{gold_rank_prod}", f"top: cur={cur_top} | prod={prod_top}"))
        if task.startswith("remove beta approval") and headline is None:
            headline = {"scores": scores, "detail": detail, "cur": cur[:6], "prod": prod[:6], "gold": gold}

    n = valid
    def pct(x): return round(100.0 * x / n, 1)
    print(f"\n=== Production-aware ranking benchmark — {n} valid tasks (scan: jarvis_desktop) ===")
    print(f"{'metric':<16}{'CURRENT':>12}{'PROD-AWARE':>14}")
    for key, label in (("h1", "Hit@1"), ("h3", "Hit@3"), ("h5", "Hit@5")):
        print(f"{label:<16}{pct(agg['cur'][key]):>11}%{pct(agg['prod'][key]):>13}%")
    print(f"{'File recall@5':<16}{round(100*agg['cur']['rec']/n,1):>11}%{round(100*agg['prod']['rec']/n,1):>13}%")
    print(f"{'Symbol recall':<16}{pct(sym_hits):>11}%{pct(sym_hits):>13}%  (ranking-independent)")

    print("\n=== Per-task gold rank (1=best; 0=not in list) ===")
    for task, rankinfo, extra in rows:
        print(f"  {task[:46]:<46} {rankinfo:<22} {extra}")

    if headline:
        print("\n=== HEADLINE TASK: 'remove beta approval completely' — exact scores ===")
        sc = headline["scores"]; dt = headline["detail"]
        shown = sorted(sc.items(), key=lambda x: -x[1])[:10]
        for p, s in shown:
            pen = ownership_penalty(p)
            d = dt.get(p, {})
            print(f"  {s:6.1f}  -pen{pen:<4} ={s-pen:6.1f}  role={str(d.get('role')):<16} {p}")
            for r in (d.get('reasons') or [])[:4]:
                print(f"            · {r}")
        print(f"  CURRENT top-6:    {headline['cur']}")
        print(f"  PROD-AWARE top-6: {headline['prod']}")
        print(f"  gold: {headline['gold']}")

    out = {"n": n, "agg": agg, "sym_hits": sym_hits, "rows": rows}
    dst = os.path.join(REPO, "reports", "final_launch_audit", "ranking_benchmark_raw.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nsaved {dst}")


if __name__ == "__main__":
    main()
