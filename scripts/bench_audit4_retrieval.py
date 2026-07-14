"""
AUDIT 4 — Objective RETRIEVAL benchmark: Atlas vs no-Atlas mechanical baselines.

Scope (honest): this measures the RETRIEVAL LAYER only -- given a realistic task,
does the method surface the file(s) where the relevant code actually lives?
It does NOT measure end-to-end agent task success/correctness (that needs isolated
agentic runs + blind human grading + an API key; see report).

Methodology:
- Ground truth (gold) is ATLAS-INDEPENDENT: for symbol tasks, gold = file(s) where
  `class X` / `def X` is defined, resolved by regex over the repo's own source
  (test files excluded when a non-test definition exists). For behavioral tasks,
  gold = a hand-verified path that must exist. Tasks whose gold cannot be resolved
  are dropped (GOLD-MISSING) -- never counted.
- Baseline A (naive grep)  = rank files by task-keyword occurrence count, top-8.
- Baseline B (BM25)        = Okapi BM25 over the same files, top-8. Stronger than
  grep; a closer (still LOW) proxy for what a no-Atlas agent retrieves.
- Atlas = build_context_pack_from_state(task).recommended_files (read-only; the
  retrieval/ranking code is NOT modified during this audit).

Paired metrics per task (Atlas vs each baseline, same task):
  Hit@1/3/5, Recall@5, reciprocal rank (-> MRR), gold rank, wrong-files-before-hit,
  files returned, noise@5 (test/demo/doc/vendor in top-5), tokens / context size,
  hallucinated files (must be 0).

Statistics: paired bootstrap 95% CI on mean(Atlas-baseline) for each metric, exact
sign test and Wilcoxon signed-rank (normal approx) on per-task deltas, McNemar exact
on Hit@5. n reported; significance flagged at p<0.05.

Run: py -3 scripts/bench_audit4_retrieval.py
"""
from __future__ import annotations
import json, math, os, re, sys, time, random

from verification_isolation import activate_isolated_atlas_data

activate_isolated_atlas_data("bench-audit4-retrieval")

ROOT = r"C:\J.A.R.V.I.S\local_atlas"
sys.path.insert(0, ROOT)
from atlas_desktop import api, context_pack as cp  # noqa: E402

EXT = os.path.join(ROOT, "external_repos")
random.seed(1234)

STOP = set("the a an of to in for and or where is are was how do does find fix add "
           "locate trace what breaks if file files implemented implementation handling "
           "class def function method object module code base where's wheres there "
           "from into this that with on at it its as be can get when which while "
           "i want need please make sure should would could the".split())
NOISE = {"test", "tests", "testing", "demo", "demos", "sample", "samples", "sample_repo",
         "small_repo", "medium_repo", "large_repo", "examples", "example", "fixtures",
         "docs", "doc", "site", "staging", "vendor", "node_modules", "_internal", "bench"}

# (repo_path, label, [(task_text, symbol_or_None, [explicit_gold_or_empty])])
SUITES = [
    (os.path.join(EXT, "requests"), "requests", [
        ("where is HTTP basic authentication implemented", "HTTPBasicAuth", []),
        ("fix a bug in the requests cookie jar", "RequestsCookieJar", []),
        ("the base RequestException class", "RequestException", []),
        ("locate the Session class that persists connections", "Session", []),
        ("how is the HTTPAdapter transport implemented", "HTTPAdapter", []),
        ("the Response object is not decoding gzip correctly", "Response", []),
        ("where is the PreparedRequest built", "PreparedRequest", []),
        ("general utility helpers like to_key_val_list", "to_key_val_list", []),
    ]),
    (os.path.join(EXT, "flask"), "flask", [
        ("where is the Flask application object implemented", "Flask", []),
        ("registering and nesting a Blueprint", "Blueprint", []),
        ("loading Config from environment or a python file", "Config", []),
        ("the request context is popped too early", "RequestContext", []),
        ("server side secure cookie session interface", "SecureCookieSessionInterface", []),
        ("class based MethodView dispatch", "MethodView", []),
        ("where the flask CLI ScriptInfo lives", "ScriptInfo", []),
        ("rendering a jinja template string", None, ["src/flask/templating.py"]),
    ]),
    (os.path.join(EXT, "fastapi"), "fastapi", [
        ("where is the FastAPI application class defined", "FastAPI", []),
        ("how does APIRouter include routes", "APIRouter", []),
        ("the Depends dependency injection marker", "Depends", []),
        ("jsonable_encoder breaks on a custom type", "jsonable_encoder", []),
        ("raising an HTTPException with a status code", "HTTPException", []),
        ("OAuth2 password bearer security scheme", "OAuth2PasswordBearer", []),
    ]),
    (os.path.join(EXT, "pydantic"), "pydantic", [
        ("where is the BaseModel class implemented", "BaseModel", []),
        ("customizing a field with the Field function", "Field", []),
        ("the field_validator decorator", "field_validator", []),
        ("TypeAdapter for validating arbitrary types", "TypeAdapter", []),
        ("how is a ValidationError surfaced", "ValidationError", []),
    ]),
    (os.path.join(EXT, "rich"), "rich", [
        ("where is the Console class implemented", "Console", []),
        ("rendering a Table with columns", "Table", []),
        ("a Progress bar with multiple tasks", "Progress", []),
        ("syntax highlighting with the Syntax class", "Syntax", []),
        ("styled Text spans and markup", "Text", []),
    ]),
    (os.path.join(EXT, "typer"), "typer", [
        ("where is the main Typer application class", "Typer", []),
        ("declaring a CLI Option", "Option", []),
        ("declaring a positional Argument", "Argument", []),
    ]),
    (os.path.join(EXT, "celery"), "celery", [
        ("where is the Celery application object", "Celery", []),
        ("polling an AsyncResult for a task result", "AsyncResult", []),
        ("composing task signatures and chains in canvas", "Signature", []),
        ("the base Task class with retry logic", "Task", []),
    ]),
    (os.path.join(EXT, "sqlmodel"), "sqlmodel", [
        ("where is the SQLModel base class defined", "SQLModel", []),
        ("declaring a SQLModel Field with a default", "Field", []),
        ("the relationship between two SQLModel tables", "Relationship", []),
    ]),
    (os.path.join(EXT, "django"), "django", [
        ("the QuerySet lazy evaluation and filtering", "QuerySet", []),
        ("the base Model metaclass and save method", None, ["django/db/models/base.py"]),
        ("an HttpResponse with custom headers", "HttpResponse", []),
        ("parsing an incoming HttpRequest", "HttpRequest", []),
        ("URL pattern resolution and reverse", "URLResolver", []),
        ("a Form field is not validating", None, ["django/forms/forms.py"]),
        ("the template tag library registration", None, ["django/template/defaulttags.py"]),
        ("how database migrations are applied", "MigrationExecutor", []),
    ]),
    (os.path.join(EXT, "langchain"), "langchain", [
        ("where is the BaseLLM language model class", "BaseLLM", []),
        ("the BasePromptTemplate for prompts", "BasePromptTemplate", []),
        ("the Runnable interface and pipe operator", "Runnable", []),
        ("the BaseChatModel chat interface", "BaseChatModel", []),
        ("the core Document abstraction", "Document", []),
    ]),
    (os.path.join(ROOT, "atlas_desktop"), "atlas", [
        ("rank task relevant files when building a context pack", "build_context_pack", []),
        ("analyze the root cause from a python stack trace", None, ["root_cause.py"]),
        ("repository memory freshness and drift detection", None, ["repository_memory.py"]),
        ("the evidence engine symbol index", None, ["evidence_engine/symbol_index.py"]),
        ("impact analysis of what breaks if a file changes", None, ["impact_engine/engine.py"]),
        ("usage limits and quota enforcement", None, ["usage/limits.py"]),
        ("desktop website login auth handoff mode", None, ["accounts_client.py"]),
        ("billing plan definitions and prices", None, ["billing/plans.py"]),
    ]),
]


def norm(p): return p.replace("\\", "/").lower()


def keywords(task):
    return [w for w in re.split(r"[^a-z0-9_]+", task.lower()) if len(w) > 2 and w not in STOP]


def is_noise(path):
    return bool(set(norm(path).split("/")) & NOISE)


def resolve_gold(symbol, files_text):
    """Atlas-independent gold: files defining `class symbol` / `def symbol`.
    Prefer non-test definitions when any exist."""
    pat = re.compile(r"^\s*(?:class|def)\s+" + re.escape(symbol.lower()) + r"\b", re.M)
    hits = [p for p, t in files_text.items() if pat.search(t)]
    nontest = [p for p in hits if not is_noise(p)]
    return nontest if nontest else hits


def load_all_text(repo, paths):
    out = {}
    for p in paths:
        ap = os.path.join(repo, p.replace("/", os.sep))
        try:
            if os.path.getsize(ap) > 400_000:
                continue
            with open(ap, encoding="utf-8", errors="ignore") as f:
                out[norm(p)] = f.read().lower()
        except OSError:
            pass
    return out


def grep_rank(files_text, task):
    kw = keywords(task)
    scored = []
    for p, t in files_text.items():
        c = sum(t.count(k) for k in kw)
        if c:
            scored.append((c, p))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:8]]


_TOKRE = re.compile(r"[a-z0-9_]+")


def build_bm25(files_text):
    docs = {p: _TOKRE.findall(t) for p, t in files_text.items()}
    df = {}
    for toks in docs.values():
        for term in set(toks):
            df[term] = df.get(term, 0) + 1
    N = max(1, len(docs))
    avgdl = (sum(len(t) for t in docs.values()) / N) or 1.0
    tf = {p: {} for p in docs}
    for p, toks in docs.items():
        d = tf[p]
        for term in toks:
            d[term] = d.get(term, 0) + 1
    return {"docs": docs, "df": df, "N": N, "avgdl": avgdl, "tf": tf, "len": {p: len(t) for p, t in docs.items()}}


def bm25_rank(bm, task, k1=1.5, b=0.75):
    kw = keywords(task)
    idf = {}
    for term in kw:
        n = bm["df"].get(term, 0)
        idf[term] = math.log((bm["N"] - n + 0.5) / (n + 0.5) + 1.0)
    scored = []
    for p in bm["docs"]:
        dl = bm["len"][p] or 1
        s = 0.0
        tfp = bm["tf"][p]
        for term in kw:
            f = tfp.get(term, 0)
            if not f:
                continue
            s += idf[term] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / bm["avgdl"]))
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:8]]


def first_rank(ranked, gold):
    for i, p in enumerate(ranked, 1):
        if p in gold:
            return i
    return 0  # not found


def metrics_for(ranked, gold, k_open):
    r = first_rank(ranked, gold)
    found = r > 0
    rr = (1.0 / r) if found else 0.0
    wrong_before = (r - 1) if found else min(len(ranked), k_open)  # wrong files opened before hit
    rec5 = len([g for g in gold if g in set(ranked[:5])]) / len(gold)
    noise5 = sum(1 for p in ranked[:5] if is_noise(p))
    return {
        "hit1": int(found and r <= 1), "hit3": int(found and r <= 3), "hit5": int(found and r <= 5),
        "rr": rr, "rank": r, "rec5": rec5, "wrong_before": wrong_before, "noise5": noise5,
        "n_returned": len(ranked),
    }


# ---------------- statistics (dependency-free) ----------------

def mean(xs): return sum(xs) / len(xs) if xs else 0.0


def bootstrap_ci(diffs, iters=10000):
    if not diffs:
        return (0.0, 0.0)
    n = len(diffs)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += diffs[random.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters)]
    return (lo, hi)


def sign_test(diffs):
    """Two-sided exact sign test on nonzero diffs (positive = Atlas better)."""
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    n = pos + neg
    if n == 0:
        return (pos, neg, 1.0)
    k = min(pos, neg)
    p = 0.0
    for i in range(0, k + 1):
        p += math.comb(n, i)
    p = min(1.0, 2.0 * p * (0.5 ** n))
    return (pos, neg, p)


def normal_sf(z): return 0.5 * math.erfc(z / math.sqrt(2))


def wilcoxon(diffs):
    """Wilcoxon signed-rank, normal approximation w/ continuity correction. positive=Atlas better."""
    nz = [d for d in diffs if d != 0]
    n = len(nz)
    if n < 6:
        return None
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    Wp = sum(ranks[i] for i in range(n) if nz[i] > 0)
    Wm = sum(ranks[i] for i in range(n) if nz[i] < 0)
    W = min(Wp, Wm)
    mu = n * (n + 1) / 4.0
    sig = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if sig == 0:
        return None
    z = (W - mu + 0.5) / sig
    return 2 * normal_sf(abs(z))


def mcnemar_exact(a_hits, b_hits):
    """Exact McNemar (binomial on discordant pairs). Atlas hit but baseline miss = b; reverse = c."""
    b = sum(1 for x, y in zip(a_hits, b_hits) if x == 1 and y == 0)
    c = sum(1 for x, y in zip(a_hits, b_hits) if x == 0 and y == 1)
    n = b + c
    if n == 0:
        return (b, c, 1.0)
    k = min(b, c)
    p = 0.0
    for i in range(0, k + 1):
        p += math.comb(n, i)
    p = min(1.0, 2.0 * p * (0.5 ** n))
    return (b, c, p)


def main():
    rows = []
    per_repo = {}
    timings = {}
    for repo, label, tasks in SUITES:
        if not os.path.isdir(repo):
            print(f"SKIP {label}: missing {repo}", flush=True)
            continue
        print(f"[scan] {label} ...", flush=True)
        t0 = time.time(); api.scan_repository(repo); cold = time.time() - t0
        t1 = time.time(); api.scan_repository(repo); warm = time.time() - t1
        state = dict(api._STATE)
        files = [(f["path"] if isinstance(f, dict) else f)
                 for f in (state.get("index") or {}).get("files") or []]
        files = [p for p in files if norm(p).endswith((".py", ".js", ".ts"))]
        allpaths = {norm(p) for p in files}
        ftext = load_all_text(repo, files)
        bm = build_bm25(ftext)
        timings[label] = {"cold": round(cold, 2), "warm": round(warm, 2),
                          "files_indexed": len(files), "files_read": len(ftext)}
        print(f"  scanned {len(files)} files (cold {cold:.1f}s / warm {warm:.2f}s)", flush=True)
        per_repo.setdefault(label, [])
        for task, symbol, explicit in tasks:
            if symbol:
                gold = resolve_gold(symbol, ftext)
            else:
                gold = [norm(g) for g in explicit if norm(g) in allpaths]
            gold = [g for g in gold if g in allpaths]
            if not gold:
                rows.append({"repo": label, "task": task, "symbol": symbol, "status": "GOLD-MISSING"})
                print(f"  GOLD-MISSING [{label}] {symbol or explicit}: {task[:48]}", flush=True)
                continue
            names_symbol = bool(symbol and symbol.lower() in task.lower())
            tb = time.time()
            pack = cp.build_context_pack_from_state(repo, task, dict(state), memory={},
                                                    include_snippets=False, max_files=12)
            build_t = time.time() - tb
            recs = pack.get("recommended_files") or []
            a_ranked = [norm(it["path"]) for it in recs]
            a_tok = int(pack.get("token_estimate") or 0)
            halluc = [p for p in a_ranked if p not in allpaths]
            g_ranked = grep_rank(ftext, task)
            b_ranked = bm25_rank(bm, task)
            g_tok = sum(len(ftext.get(p, "")) for p in g_ranked) // 4
            b_tok = sum(len(ftext.get(p, "")) for p in b_ranked) // 4
            A = metrics_for(a_ranked, gold, 12)
            G = metrics_for(g_ranked, gold, 8)
            B = metrics_for(b_ranked, gold, 8)
            row = {"repo": label, "task": task, "symbol": symbol, "names_symbol": names_symbol,
                   "gold": gold, "n_gold": len(gold), "build_t": round(build_t, 3),
                   "conf": pack.get("confidence"), "halluc": len(halluc),
                   "atlas": {**A, "tok": a_tok}, "grep": {**G, "tok": g_tok}, "bm25": {**B, "tok": b_tok}}
            rows.append(row)
            per_repo[label].append(row)
    scored = [r for r in rows if r.get("status") != "GOLD-MISSING"]
    N = len(scored)

    def col(method, key): return [r[method][key] for r in scored]

    def report_metric(name, key, higher_better=True, integer=False):
        a = col("atlas", key); g = col("grep", key); b = col("bm25", key)
        out = {"metric": name, "atlas": mean(a), "grep": mean(g), "bm25": mean(b)}
        for base_name, base in (("grep", g), ("bm25", b)):
            diffs = [ai - bi for ai, bi in zip(a, base)]  # positive = atlas higher
            if not higher_better:
                diffs = [-d for d in diffs]  # positive = atlas better (lower)
            lo, hi = bootstrap_ci(diffs)
            pos, neg, sp = sign_test(diffs)
            wp = wilcoxon(diffs)
            out[f"vs_{base_name}"] = {
                "mean_delta_atlas_better": round(mean(diffs), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
                "sign_pos": pos, "sign_neg": neg, "sign_p": round(sp, 5),
                "wilcoxon_p": (round(wp, 5) if wp is not None else None),
                "significant": (sp < 0.05),
            }
        return out

    print("\n" + "=" * 78)
    print(f"AUDIT 4 RETRIEVAL BENCHMARK — N={N} scored tasks across {len(per_repo)} repos")
    print(f"GOLD-MISSING (excluded): {len(rows) - N}")
    print("=" * 78)

    summary = {}
    print(f"\n{'METRIC':<22}{'ATLAS':>9}{'BM25':>9}{'grep':>9}   sig vs grep / bm25")
    for name, key, hb, integer in [
        ("Hit@1", "hit1", True, True), ("Hit@3", "hit3", True, True), ("Hit@5", "hit5", True, True),
        ("MRR (recip rank)", "rr", True, False), ("Recall@5", "rec5", True, False),
        ("Gold rank (lower)", "rank", False, True), ("Wrong-before-hit", "wrong_before", False, True),
        ("Noise@5 (lower)", "noise5", False, True), ("Tokens (lower)", "tok", False, True),
    ]:
        m = report_metric(name, key, hb, integer)
        summary[key] = m
        sg = "Y" if m["vs_grep"]["significant"] else "n"
        sb = "Y" if m["vs_bm25"]["significant"] else "n"
        print(f"{name:<22}{m['atlas']:>9.3f}{m['bm25']:>9.3f}{m['grep']:>9.3f}      {sg} / {sb}")

    # McNemar on Hit@5
    mc_g = mcnemar_exact(col("atlas", "hit5"), col("grep", "hit5"))
    mc_b = mcnemar_exact(col("atlas", "hit5"), col("bm25", "hit5"))
    print(f"\nMcNemar Hit@5 vs grep: atlas-only={mc_g[0]} base-only={mc_g[1]} p={mc_g[2]:.5f}")
    print(f"McNemar Hit@5 vs bm25: atlas-only={mc_b[0]} base-only={mc_b[1]} p={mc_b[2]:.5f}")

    halluc_total = sum(r["halluc"] for r in scored)
    print(f"\nHallucinated files (Atlas, must be 0): {halluc_total}")
    a_tok_mean = mean(col("atlas", "tok")); g_tok_mean = mean(col("grep", "tok")); b_tok_mean = mean(col("bm25", "tok"))
    print(f"Token reduction vs grep: {round(100*(1-a_tok_mean/g_tok_mean),1) if g_tok_mean else 0}%  "
          f"vs bm25: {round(100*(1-a_tok_mean/b_tok_mean),1) if b_tok_mean else 0}%")

    # breakdown: tasks that name the symbol vs behavioral
    named = [r for r in scored if r.get("names_symbol")]
    behav = [r for r in scored if not r.get("names_symbol")]
    def grp(rs, method, key): return round(mean([r[method][key] for r in rs]), 3) if rs else 0.0
    print(f"\nBreakdown Hit@5 (Atlas / bm25 / grep):")
    print(f"  symbol-named tasks (n={len(named)}): {grp(named,'atlas','hit5')} / {grp(named,'bm25','hit5')} / {grp(named,'grep','hit5')}")
    print(f"  behavioral tasks  (n={len(behav)}): {grp(behav,'atlas','hit5')} / {grp(behav,'bm25','hit5')} / {grp(behav,'grep','hit5')}")

    print("\n================ PER-REPO (Hit@5 A/BM/grep · meanGoldRank A/BM · cold s) ================")
    for label, rs in per_repo.items():
        if not rs:
            continue
        n = len(rs)
        print(f"  {label:<12} n={n:<3} Hit@5 {grp(rs,'atlas','hit5')}/{grp(rs,'bm25','hit5')}/{grp(rs,'grep','hit5')}"
              f"   rank {grp(rs,'atlas','rank')}/{grp(rs,'bm25','rank')}   cold {timings[label]['cold']}s")

    out = {"N": N, "gold_missing": len(rows) - N, "repos": list(per_repo),
           "summary": summary, "mcnemar_hit5": {"vs_grep": mc_g, "vs_bm25": mc_b},
           "hallucinated": halluc_total, "timings": timings,
           "token_means": {"atlas": a_tok_mean, "grep": g_tok_mean, "bm25": b_tok_mean},
           "named_n": len(named), "behav_n": len(behav), "rows": rows}
    dst = os.path.join(ROOT, "reports", "audit4")
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, "retrieval_benchmark_raw.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nsaved {os.path.join(dst, 'retrieval_benchmark_raw.json')}")


if __name__ == "__main__":
    main()
