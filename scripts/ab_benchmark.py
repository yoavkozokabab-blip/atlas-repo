"""Blind A/B harness: Claude alone vs Claude+Atlas.  ATLAS IS FROZEN (read-only).

This makes the approved design (claude_vs_atlas_benchmark_design.md) executable.
It is deliberately split so generation and scoring are separable and the human
grade is BLIND. No step self-grades.

Subcommands:
  build      Construct both-arm prompts + objective auto-metrics per task. NO model
             needed — runnable now. Output: reports/phase186/ab_build/*.json
  run        Call the model for each arm (needs ANTHROPIC_API_KEY + `anthropic`).
             Output: ab_run/answers.jsonl + ab_run/key.json (arm<->submission map).
  anonymize  Strip arm identity, normalize answers, emit a BLIND scoring packet
             (one .md per submission) + ab_scoring_sheet.csv for graders.
  analyze    Ingest >=2 filled grader CSVs; compute per-dimension deltas, paired
             sign test, inter-rater agreement (Cohen's kappa), and the verdict.

Owner supplies: an API key (run), and >=2 independent human graders (score).
"""
import csv
import glob
import json
import os
import random
import statistics as st
import sys
import time

from verification_isolation import activate_isolated_atlas_data

activate_isolated_atlas_data("ab-benchmark")

# Reuse the labeled tasks + gold + grep baseline from the retrieval benchmark.
import atlas_value_benchmark as avb
from atlas_desktop import api, context_pack as cp

OUT = "reports/phase186"
SYSTEM = (
    "You are a senior software engineer. Given a coding task and repository context, "
    "produce a precise, actionable plan. Respond ONLY in this exact template:\n"
    "## Summary\n## Relevant files\n## Relevant symbols\n## Implementation plan\n"
    "## Tests to run or add\n## Risks\n"
    "Cite real files and symbols. Do not invent files or APIs."
)
RUBRIC = ["correctness", "relevant_files", "relevant_symbols", "implementation_plan",
          "tests_suggested", "no_hallucination", "risks_covered"]


def _scan(repo_abs):
    api.scan_repository(repo_abs, None)
    return dict(api._STATE)


def cmd_build():
    os.makedirs(f"{OUT}/ab_build", exist_ok=True)
    built = []
    for key, path in avb.REPOS.items():
        repo_abs = os.path.abspath(path)
        state = _scan(repo_abs)
        idx = {cp._norm_path(f["path"]) for f in state["index"]["files"] if f.get("path")}
        for tkey, task, gold_syms in avb.TASKS:
            if tkey != key:
                continue
            gold = avb.resolve_gold(repo_abs, gold_syms) & idx
            grep_files, _ = avb.baseline_grep(repo_abs, task, idx)
            pack = cp.build_context_pack_from_state(repo_abs, task, state, max_files=8)
            atlas_files = [cp._norm_path(it["path"]) for it in pack["recommended_files"]]
            atlas_ctx = pack["markdown"]
            grep_ctx = "Candidate files from repository search (ranked):\n" + "\n".join(f"- {f}" for f in grep_files)
            rec = {
                "task_id": f"{key}:{avb.TASKS.index((tkey, task, gold_syms))}",
                "repo": key, "task": task, "gold_files": sorted(gold), "gold_symbols": gold_syms,
                "armA_prompt": {"system": SYSTEM, "user": f"Task: {task}\nRepository: {key}\n\n{grep_ctx}\n\nProduce the plan."},
                "armB_prompt": {"system": SYSTEM, "user": f"Task: {task}\nRepository: {key}\n\nAtlas context:\n{atlas_ctx}\n\nProduce the plan."},
                # Objective, model-free metrics: what did each arm's CONTEXT contain?
                "armA_context_has_gold": bool(set(grep_files) & gold),
                "armB_context_has_gold": bool(set(atlas_files) & gold),
                "armA_context_tokens": cp.estimate_tokens(grep_ctx),
                "armB_context_tokens": cp.estimate_tokens(atlas_ctx),
            }
            json.dump(rec, open(f"{OUT}/ab_build/{rec['task_id'].replace(':', '_')}.json", "w"), indent=2)
            built.append(rec)
    # Objective summary (no model, no grading — fully valid)
    a = sum(r["armA_context_has_gold"] for r in built); b = sum(r["armB_context_has_gold"] for r in built)
    print(f"built {len(built)} tasks")
    print(f"context contains gold file:  armA(grep)={a}/{len(built)}  armB(atlas)={b}/{len(built)}")
    print(f"mean context tokens:  armA={round(st.mean(r['armA_context_tokens'] for r in built))}  "
          f"armB={round(st.mean(r['armB_context_tokens'] for r in built))}")
    return built


def _call_model(system, user):
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("`anthropic` not installed. pip install anthropic, set ANTHROPIC_API_KEY, retry.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set — cannot run the model arm.")
    model = os.environ.get("ATLAS_BENCH_MODEL", "claude-sonnet-4-6")
    client = Anthropic()
    t0 = time.time()
    msg = client.messages.create(model=model, max_tokens=1500, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), \
        {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens, "s": round(time.time() - t0, 2), "model": model}


def cmd_run():
    files = sorted(glob.glob(f"{OUT}/ab_build/*.json"))
    if not files:
        sys.exit("run `build` first.")
    os.makedirs(f"{OUT}/ab_run", exist_ok=True)
    rng = random.Random(42)
    answers, key = [], []
    for f in files:
        rec = json.load(open(f))
        for arm in ("A", "B"):
            ans, meta = _call_model(rec[f"arm{arm}_prompt"]["system"], rec[f"arm{arm}_prompt"]["user"])
            sid = f"S{rng.randint(100000, 999999)}"
            answers.append({"submission_id": sid, "task_id": rec["task_id"], "answer": ans, "meta": meta})
            key.append({"submission_id": sid, "task_id": rec["task_id"], "arm": arm})
    with open(f"{OUT}/ab_run/answers.jsonl", "w") as fh:
        for a in answers:
            fh.write(json.dumps(a) + "\n")
    json.dump(key, open(f"{OUT}/ab_run/key.json", "w"), indent=2)  # released only AFTER scoring
    print(f"ran {len(answers)} submissions ({len(files)} tasks x 2 arms). key.json withheld until scoring done.")


def cmd_anonymize():
    answers = [json.loads(l) for l in open(f"{OUT}/ab_run/answers.jsonl")]
    random.Random(7).shuffle(answers)  # randomize presentation order
    os.makedirs(f"{OUT}/ab_blind", exist_ok=True)
    for a in answers:
        open(f"{OUT}/ab_blind/{a['submission_id']}.md", "w").write(
            f"# Submission {a['submission_id']}\n\n(grade blind — do not infer the source)\n\n{a['answer']}\n")
    with open(f"{OUT}/ab_scoring_sheet.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["submission_id", "grader"] + RUBRIC + ["prefer_this_for_junior(y/n)"])
        for a in answers:
            w.writerow([a["submission_id"], ""] + [""] * len(RUBRIC) + [""])
    print(f"wrote {len(answers)} blind submissions + ab_scoring_sheet.csv (one row per submission per grader)")


def _kappa(g1, g2):
    # Cohen's kappa on agreement of integer scores (treat each (sid,dim) as a rating).
    keys = sorted(set(g1) & set(g2))
    if not keys:
        return None
    agree = sum(1 for k in keys if g1[k] == g2[k]) / len(keys)
    cats = set(g1[k] for k in keys) | set(g2[k] for k in keys)
    pe = sum((sum(1 for k in keys if g1[k] == c) / len(keys)) * (sum(1 for k in keys if g2[k] == c) / len(keys)) for c in cats)
    return round((agree - pe) / (1 - pe), 3) if pe < 1 else 1.0


def cmd_analyze():
    key = {r["submission_id"]: r for r in json.load(open(f"{OUT}/ab_run/key.json"))}
    sheets = glob.glob(f"{OUT}/ab_scoring_*.csv")
    graders = {}
    for s in sheets:
        for row in csv.DictReader(open(s)):
            g = row.get("grader") or os.path.basename(s)
            graders.setdefault(g, {})[row["submission_id"]] = row
    if len(graders) < 2:
        print(f"WARNING: only {len(graders)} grader(s). Design requires >=2 independent blind graders.")
    # Per-arm mean per dimension (averaged over graders)
    by_arm = {"A": {d: [] for d in RUBRIC}, "B": {d: [] for d in RUBRIC}}
    for g, rows in graders.items():
        for sid, row in rows.items():
            arm = key.get(sid, {}).get("arm")
            if not arm:
                continue
            for d in RUBRIC:
                try:
                    by_arm[arm][d].append(float(row[d]))
                except (ValueError, KeyError, TypeError):
                    pass
    print("dimension            armA  armB  delta")
    for d in RUBRIC:
        a = st.mean(by_arm["A"][d]) if by_arm["A"][d] else float("nan")
        b = st.mean(by_arm["B"][d]) if by_arm["B"][d] else float("nan")
        print(f"  {d:20s} {a:4.2f}  {b:4.2f}  {b - a:+.2f}")
    gl = list(graders.values())
    if len(gl) >= 2:
        flat = lambda rows: {f"{sid}:{d}": int(float(r[d])) for sid, r in rows.items() for d in RUBRIC if r.get(d) not in (None, "")}
        print("inter-rater Cohen's kappa:", _kappa(flat(gl[0]), flat(gl[1])))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": cmd_build, "run": cmd_run, "anonymize": cmd_anonymize, "analyze": cmd_analyze}[cmd]()
