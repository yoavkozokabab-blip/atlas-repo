"""Labeled value/retrieval benchmark: Atlas vs no-Atlas (grep) baseline.

Honest design:
- Ground truth is INDEPENDENT of Atlas: for each task the gold file(s) = where the
  canonical symbol is DEFINED, resolved by ripgrep ("class X"/"def X"), not by any
  retriever's output.
- "No-Atlas" baseline = what an agent does without Atlas: ripgrep the repo for the
  task's keywords, rank files by match count, take top-k. Deterministic, no LLM.
- Atlas = build_context_pack_from_state -> recommended files + symbol slices.
- Both score against the same gold, over the same indexed-file universe.
- Model-dependent dimensions (end-to-end correctness, plan quality, missed risks)
  are NOT scored here — that needs blind model trials (see report).

Usage: PYTHONPATH=. py -3 scripts/atlas_value_benchmark.py
Writes JSON to reports/phase186/atlas_value_benchmark_raw.json
"""
import glob
import json
import os
import re
import shutil
import subprocess
import time

from atlas_desktop import api, context_pack as cp


def _resolve_rg():
    """Find a real ripgrep binary. The shell `rg` is a function (proxied through
    claude.exe) and invisible to subprocess, so resolve an actual rg.exe."""
    cand = shutil.which("rg")
    if cand:
        return cand
    patterns = [
        os.path.expanduser(r"~/AppData/Local/Programs/*/resources/app/node_modules/@vscode/ripgrep/bin/rg.exe"),
        os.path.expanduser(r"~/AppData/Local/Programs/*/**/@vscode/ripgrep/bin/rg.exe"),
        r"C:/Program Files/Git/usr/bin/rg.exe",
    ]
    for pat in patterns:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise RuntimeError("ripgrep (rg.exe) not found — gold resolution would be empty. Aborting.")


RG = _resolve_rg()

REPOS = {
    "requests": "external_repos/requests",
    "atlas": "atlas_desktop",
    "langchain": "external_repos/langchain",
    "home_assistant": "external_repos/home_assistant",
}

# task, gold_symbols (resolved to gold files by grep at runtime)
TASKS = [
    ("requests", "fix connection retry and backoff in the HTTP adapter", ["HTTPAdapter"]),
    ("requests", "cookies are not persisted across requests in a session", ["RequestsCookieJar"]),
    ("requests", "handle redirect history when following 302 responses", ["SessionRedirectMixin"]),
    ("requests", "Response.json raises the wrong error on an invalid JSON body", ["Response"]),
    ("requests", "prepare a multipart file upload request body", ["PreparedRequest"]),
    ("atlas", "improve symbol slicing token reduction in context packs", ["compute_symbol_slices"]),
    ("atlas", "root cause analysis from an exception stack trace", ["analyze_root_cause"]),
    ("atlas", "classify task type to pick a retrieval strategy", ["_classify_task_type"]),
    ("atlas", "MCP server tool dispatch and JSON-RPC handling", ["handle_jsonrpc"]),
    ("atlas", "desktop authenticates against the website with a bearer token", ["auth_mode"]),
    ("langchain", "streaming callback handler in the base chat model", ["BaseChatModel"]),
    ("langchain", "parse JSON output returned by an LLM", ["JsonOutputParser"]),
    ("langchain", "retry logic when the base LLM hits a rate limit", ["BaseLLM"]),
    ("langchain", "in-memory vector store similarity search", ["InMemoryVectorStore"]),
    ("langchain", "prompt template variable formatting", ["BasePromptTemplate"]),
    ("home_assistant", "sensor entity state is not updating", ["SensorEntity"]),
    ("home_assistant", "config entry setup and unload flow", ["ConfigEntry"]),
    ("home_assistant", "climate entity target temperature handling", ["ClimateEntity"]),
    ("home_assistant", "entity base class writes state to the machine", ["Entity"]),
    ("home_assistant", "event bus fire and listen", ["EventBus"]),
]

_STOP = {"fix", "the", "and", "for", "with", "from", "into", "when", "that", "this",
         "should", "does", "not", "are", "is", "a", "an", "of", "in", "on", "to", "by"}
TOPK = 8


def norm(p):
    return p.replace("\\", "/")


def rel(repo_abs, p):
    p = norm(p)
    r = norm(repo_abs)
    if p.lower().startswith(r.lower()):
        p = p[len(r):].lstrip("/")
    return p


def resolve_gold(repo_abs, symbols):
    gold = set()
    for sym in symbols:
        try:
            out = subprocess.run(
                [RG, "-l", rf"(class|def)\s+{re.escape(sym)}\b", repo_abs],
                capture_output=True, text=True, timeout=120,
            ).stdout
            for line in out.splitlines():
                if line.strip():
                    gold.add(rel(repo_abs, line.strip()))
        except Exception:
            pass
    return gold


def baseline_grep(repo_abs, task, index_files):
    terms = [t for t in re.split(r"[^a-zA-Z0-9_]+", task.lower()) if len(t) >= 4 and t not in _STOP][:8]
    if not terms:
        return [], 0.0
    args = [RG, "-c", "-i", "--no-heading"]
    for t in terms:
        args += ["-e", t]
    args.append(repo_abs)
    t0 = time.time()
    counts = {}
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=180).stdout
        for line in out.splitlines():
            if ":" not in line:
                continue
            path, _, c = line.rpartition(":")
            rp = rel(repo_abs, path)
            if rp in index_files and c.isdigit():
                counts[rp] = counts.get(rp, 0) + int(c)
    except Exception:
        pass
    dt = time.time() - t0
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOPK]
    return [p for p, _ in ranked], dt


def leaf(sym):
    return sym.split(".")[-1].lower()


def file_tokens(repo_abs, rels):
    tot = 0
    for r in rels:
        tot += cp.estimate_tokens(cp._read_small_file(repo_abs, r, max_chars=200_000))
    return tot


def main():
    results = []
    for key, path in REPOS.items():
        repo_abs = os.path.abspath(path)
        t0 = time.time()
        scan = api.scan_repository(repo_abs, None)
        scan_s = time.time() - t0
        if not scan.get("ok"):
            print(f"scan failed {key}: {scan.get('error')}")
            continue
        state = dict(api._STATE)
        index_files = {cp._norm_path(f.get("path", "")) for f in (state.get("index") or {}).get("files") or [] if f.get("path")}
        print(f"[scanned] {key}: {scan.get('file_count')} files in {scan_s:.1f}s")

        for tkey, task, gold_syms in TASKS:
            if tkey != key:
                continue
            gold = resolve_gold(repo_abs, gold_syms)
            gold &= index_files  # only gold that is actually indexed (fair universe)
            # Atlas
            tb = time.time()
            pack = cp.build_context_pack_from_state(repo_abs, task, state, max_files=TOPK)
            build_s = time.time() - tb
            a_files = [cp._norm_path(it["path"]) for it in pack["recommended_files"]]
            a_syms = set()
            for it in pack["recommended_files"]:
                for s in it.get("matched_symbols") or []:
                    n = s.get("qualname") or s.get("name")
                    if n:
                        a_syms.add(leaf(n))
                for s in it.get("symbol_slices") or []:
                    if s.get("symbol"):
                        a_syms.add(leaf(s["symbol"]))
            # fabrication: every Atlas file must be a real indexed repo file
            fabricated = [f for f in a_files if f not in index_files]
            # Baseline
            b_files, b_s = baseline_grep(repo_abs, task, index_files)

            def recall(found):
                return (len(set(found) & gold) / len(gold)) if gold else None

            def hit1(found):
                return bool(found and found[0] in gold)

            rec = {
                "repo": key, "task": task, "gold_symbols": gold_syms,
                "gold_files": sorted(gold),
                "atlas_files": a_files, "atlas_recall": recall(a_files), "atlas_hit@1": hit1(a_files),
                "atlas_symbol_recall": (sum(1 for s in gold_syms if leaf(s) in a_syms) / len(gold_syms)) if gold_syms else None,
                "atlas_pack_tokens": pack["token_estimate"],
                "atlas_build_s": round(build_s, 3),
                "atlas_fabricated_files": fabricated,
                "atlas_slice_reduction_pct": (pack.get("symbol_slicing") or {}).get("token_reduction_pct", 0.0),
                "task_type": pack["task_signals"]["task_type"],
                "baseline_files": b_files, "baseline_recall": recall(b_files), "baseline_hit@1": hit1(b_files),
                "baseline_open_tokens": file_tokens(repo_abs, b_files),
                "baseline_grep_s": round(b_s, 3),
            }
            results.append(rec)
            print(f"  [{key}] gold={sorted(gold)} | atlas_recall={rec['atlas_recall']} hit@1={rec['atlas_hit@1']} symrec={rec['atlas_symbol_recall']} | base_recall={rec['baseline_recall']} hit@1={rec['baseline_hit@1']}")

    out = "reports/phase186/atlas_value_benchmark_raw.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(results, open(out, "w"), indent=2)
    # Aggregate
    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None
    agg = {}
    for r in results:
        a = agg.setdefault(r["repo"], {"n": 0, "ar": [], "ah": [], "asr": [], "br": [], "bh": [], "apt": [], "bot": [], "fab": 0})
        a["n"] += 1
        a["ar"].append(r["atlas_recall"]); a["ah"].append(1 if r["atlas_hit@1"] else 0)
        a["asr"].append(r["atlas_symbol_recall"]); a["br"].append(r["baseline_recall"])
        a["bh"].append(1 if r["baseline_hit@1"] else 0); a["apt"].append(r["atlas_pack_tokens"])
        a["bot"].append(r["baseline_open_tokens"]); a["fab"] += len(r["atlas_fabricated_files"])
    print("\n=== AGGREGATE ===")
    for repo, a in agg.items():
        print(f"{repo} (n={a['n']}): atlas_recall={avg(a['ar'])} atlas_hit@1={avg(a['ah'])} sym_recall={avg(a['asr'])} "
              f"| base_recall={avg(a['br'])} base_hit@1={avg(a['bh'])} "
              f"| atlas_tokens={avg(a['apt'])} base_open_tokens={avg(a['bot'])} fabrications={a['fab']}")
    allr = [r for r in results]
    print(f"\nOVERALL n={len(allr)}: "
          f"atlas_recall={avg([r['atlas_recall'] for r in allr])} atlas_hit@1={avg([1 if r['atlas_hit@1'] else 0 for r in allr])} "
          f"sym_recall={avg([r['atlas_symbol_recall'] for r in allr])} "
          f"| base_recall={avg([r['baseline_recall'] for r in allr])} base_hit@1={avg([1 if r['baseline_hit@1'] else 0 for r in allr])} "
          f"| atlas_tokens={avg([r['atlas_pack_tokens'] for r in allr])} base_open_tokens={avg([r['baseline_open_tokens'] for r in allr])} "
          f"| total_fabrications={sum(len(r['atlas_fabricated_files']) for r in allr)}")


if __name__ == "__main__":
    main()
