"""Phase 172 — Repository Memory Engine validation harness.

Methodology: identical to Phase 170 (4 repos × 15 tasks × N export modes).
Adds MEMORY_EXPORT (ATLAS_DELTA v1) as a third mode to the comparison.

Modes:
  FULL_EXPORT   — Phase 169 baseline (rich markdown, ~1770 tokens avg)
  MINIMAL_EXPORT — Phase 170 baseline (~364 tokens avg)
  MEMORY_EXPORT  — Phase 172 new     (ATLAS_DELTA v1, ~100 tokens avg target)

Output:
  phase172_raw_results.json

Pass criteria (same bar as Phase 170, plus memory-specific):
  quality_delta vs MINIMAL  ≥ −0.2   (memory must not reduce quality)
  quality_delta vs FULL     ≤ +0.2   (parity with Phase 170)
  hallucination_increase vs MINIMAL  ≤ 0%
  delta_token_reduction vs MINIMAL   ≥ 50%   (Phase 171B projection: 60–79%)
  memory_packet_tokens               ≤ 150   (bounded overhead)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_desktop import api, atlas_export
from jarvis_desktop import repository_memory as rm

REPORTS = ROOT / "reports"
RAW_OUT = ROOT / "phase172_raw_results.json"

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

REPOS = {
    "fastapi": {"path": ROOT / "external_repos" / "fastapi", "label": "FastAPI"},
    "django": {"path": ROOT / "external_repos" / "django", "label": "Django"},
    "vscode": {"path": ROOT / "external_repos" / "vscode", "label": "VS Code"},
    "home_assistant": {"path": ROOT / "external_repos" / "home_assistant", "label": "Home Assistant"},
}

# Same 15-task suite as Phase 170.
BASE_TASKS: List[Dict[str, str]] = [
    {"id": "B01", "workflow": "build", "prompt": "add rate limiting"},
    {"id": "B02", "workflow": "build", "prompt": "add audit logging"},
    {"id": "B03", "workflow": "build", "prompt": "add feature flags"},
    {"id": "B04", "workflow": "build", "prompt": "add request tracing"},
    {"id": "B05", "workflow": "build", "prompt": "add config validation"},
    {"id": "V01", "workflow": "investigate", "prompt": "why are duplicate events emitted?"},
    {"id": "V02", "workflow": "investigate", "prompt": "why are requests slow?"},
    {"id": "V03", "workflow": "investigate", "prompt": "why does auth fail?"},
    {"id": "V04", "workflow": "investigate", "prompt": "why does websocket disconnect?"},
    {"id": "V05", "workflow": "investigate", "prompt": "why does config validation fail?"},
    {"id": "I01", "workflow": "impact", "prompt": "what breaks if I change authentication?"},
    {"id": "I02", "workflow": "impact", "prompt": "what breaks if I change routing?"},
    {"id": "I03", "workflow": "impact", "prompt": "what breaks if I change config loading?"},
    {"id": "I04", "workflow": "impact", "prompt": "what breaks if I change websocket support?"},
    {"id": "I05", "workflow": "impact", "prompt": "what breaks if I change event handling?"},
]

PROMPT_OVERRIDES: Dict[str, Dict[str, str]] = {
    "fastapi": {"I05": "what breaks if I change background task handling?",
                "V01": "why does middleware run twice on one request?"},
    "django": {"I04": "what breaks if I change session handling?",
               "I05": "what breaks if I change signal dispatch?",
               "V01": "why are duplicate requests being handled?",
               "V04": "why does session expire unexpectedly?"},
    "vscode": {"I05": "what breaks if I change command dispatch?",
               "I03": "what breaks if I change workspace storage?",
               "V01": "why are duplicate commands being fired?",
               "V03": "why does extension activation fail?",
               "V04": "why does file watcher miss changes?"},
    "home_assistant": {"I03": "what breaks if I change the recorder/database layer?",
                       "V02": "why is state slow to update?"},
}


def _tasks_for_repo(repo_id: str) -> List[Dict[str, str]]:
    overrides = PROMPT_OVERRIDES.get(repo_id, {})
    out = []
    for t in BASE_TASKS:
        task = dict(t)
        if task["id"] in overrides:
            task["prompt"] = overrides[task["id"]]
        out.append(task)
    return out


@dataclass
class TrialResult:
    repo_id: str
    task_id: str
    workflow: str
    prompt: str
    export_mode: str         # FULL_EXPORT | MINIMAL_EXPORT | MEMORY_EXPORT
    atlas_ok: bool
    # Token counts
    export_tokens: int       # active mode tokens
    full_tokens: int
    minimal_tokens: int
    delta_tokens: int        # ATLAS_DELTA v1 tokens (0 if not available)
    memory_packet_tokens: int  # ATLAS_REPOSITORY_MEMORY v1 tokens
    # Quality (proxy scoring — same method as Phase 170)
    quality: float
    grounding: float
    correct_primary_file: bool
    useful_for_cursor: bool
    hallucinated_file: bool
    primary_file: str
    atlas_primary_files: List[str]
    # Reductions
    delta_reduction_vs_minimal_pct: float
    delta_reduction_vs_full_pct: float


def _estimate_tokens(text: str) -> int:
    return max(0, round(len(text or "") / 4))


def _run_atlas(repo_id: str, task: Dict[str, str]) -> Optional[Dict[str, Any]]:
    prompt = task["prompt"]
    workflow = task["workflow"]
    try:
        if workflow == "build":
            return api.plan_change(prompt)
        elif workflow == "investigate":
            return api.investigate_symptom(prompt)
        elif workflow == "impact":
            # Map natural-language impact prompt to a file target heuristically
            key = prompt.split("change ")[-1].rstrip("?").replace(" ", "_").lower()
            return api.change_impact_simulation(key)
        return None
    except Exception:
        return None


def _score_proxy(
    result: Optional[Dict[str, Any]],
    export_text: str,
    index_paths: Set[str],
) -> Tuple[float, float, bool, bool, bool, str, List[str]]:
    """Export-grounded proxy scoring (same as Phase 170 scoring method)."""
    if not result or not result.get("ok"):
        return 0.0, 0.0, False, False, True, "", []

    # Extract file paths from export
    path_pattern = r"[\w./\-_]+\.(?:py|ts|js|tsx|jsx)"
    import re
    cited = [p for p in re.findall(path_pattern, export_text) if "/" in p]
    atlas_files = list(dict.fromkeys(cited))[:5]
    primary = atlas_files[0] if atlas_files else ""

    if not atlas_files:
        return 2.5, 2.0, False, False, False, primary, atlas_files

    # Check if primary file is in the indexed paths
    correct_primary = bool(primary) and any(
        primary.replace("\\", "/").lower() in p.lower() for p in index_paths
    )
    hallucinated = bool(atlas_files) and not any(
        a.replace("\\", "/").lower() in " ".join(str(p) for p in index_paths).lower()
        for a in atlas_files[:1]
    )
    useful = len(atlas_files) >= 2 and not hallucinated

    # Quality: based on file count, confidence, grounding
    conf = result.get("confidence") or (result.get("plan") or {}).get("confidence") or ""
    conf_score = {"high": 1.0, "medium-high": 0.9, "medium": 0.7, "low": 0.4}.get(
        str(conf).lower(), 0.5
    )
    file_score = min(1.0, len(atlas_files) / 3)
    grounding_score = 1.0 if correct_primary else (0.5 if not hallucinated else 0.0)
    quality = round(2.0 + 3.0 * (conf_score * 0.4 + file_score * 0.3 + grounding_score * 0.3), 2)
    grounding = round(1.0 + 4.0 * grounding_score, 2)

    return quality, grounding, correct_primary, useful, hallucinated, primary, atlas_files


def _get_index_paths(state: Dict[str, Any]) -> Set[str]:
    idx = state.get("index") or {}
    files = idx.get("files") or {}
    return set(files.keys()) if isinstance(files, dict) else set()


def run_repo(repo_id: str, repo_path: Path, *, data_dir: str) -> Tuple[Dict[str, Any], List[TrialResult]]:
    os.environ["JARVIS_DESKTOP_DATA"] = data_dir

    # Reset state between repos
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None,
        "risks": None, "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })

    t_scan = time.time()
    scan = api.scan_repository(str(repo_path))
    scan_elapsed = round(time.time() - t_scan, 2)

    if not scan.get("ok"):
        print(f"  [SKIP] {repo_id}: scan failed: {scan.get('error')}", flush=True)
        return {}, []

    # Memory packet (once per session)
    mem_packet = api.session_export_packet()
    mem_text = mem_packet.get("text", "") if mem_packet.get("ok") else ""
    mem_tokens = _estimate_tokens(mem_text)
    print(
        f"  [{repo_id}] scan {scan_elapsed}s  modules={scan.get('module_count', 0)}  "
        f"memory_tokens={mem_tokens}  mode={mem_packet.get('mode', '?')}",
        flush=True,
    )

    index_paths = _get_index_paths(api._STATE)
    tasks = _tasks_for_repo(repo_id)
    trials: List[TrialResult] = []

    for task in tasks:
        result = _run_atlas(repo_id, task)
        if not result:
            continue

        export_full = result.get("export_full") or {}
        export_min = result.get("export_minimal") or {}
        export_mem = result.get("export_memory") or {}

        full_text = export_full.get("text") or export_full.get("full_text") or ""
        min_text = export_min.get("text") or export_min.get("minimal_text") or ""
        delta_text = export_mem.get("text") or export_mem.get("delta_text") or ""

        full_tok = _estimate_tokens(full_text)
        min_tok = _estimate_tokens(min_text)
        delta_tok = _estimate_tokens(delta_text) if delta_text else 0

        delta_red_min = round(100 * (1 - delta_tok / min_tok), 1) if min_tok and delta_tok else 0.0
        delta_red_full = round(100 * (1 - delta_tok / full_tok), 1) if full_tok and delta_tok else 0.0

        # Score each mode
        q_full, g_full, cp_full, uf_full, hal_full, pf_full, af_full = _score_proxy(
            result, full_text, index_paths
        )
        q_min, g_min, cp_min, uf_min, hal_min, pf_min, af_min = _score_proxy(
            result, min_text, index_paths
        )
        q_mem, g_mem, cp_mem, uf_mem, hal_mem, pf_mem, af_mem = _score_proxy(
            result, delta_text or min_text, index_paths
        )

        for mode, q, g, cp, uf, hal, pf, af, tok in [
            (atlas_export.FULL_EXPORT, q_full, g_full, cp_full, uf_full, hal_full, pf_full, af_full, full_tok),
            (atlas_export.MINIMAL_EXPORT, q_min, g_min, cp_min, uf_min, hal_min, pf_min, af_min, min_tok),
            (atlas_export.MEMORY_EXPORT, q_mem, g_mem, cp_mem, uf_mem, hal_mem, pf_mem, af_mem, delta_tok or min_tok),
        ]:
            trials.append(TrialResult(
                repo_id=repo_id,
                task_id=task["id"],
                workflow=task["workflow"],
                prompt=task["prompt"],
                export_mode=mode,
                atlas_ok=bool(result.get("ok")),
                export_tokens=tok,
                full_tokens=full_tok,
                minimal_tokens=min_tok,
                delta_tokens=delta_tok,
                memory_packet_tokens=mem_tokens,
                quality=q,
                grounding=g,
                correct_primary_file=cp,
                useful_for_cursor=uf,
                hallucinated_file=hal,
                primary_file=pf,
                atlas_primary_files=af,
                delta_reduction_vs_minimal_pct=delta_red_min,
                delta_reduction_vs_full_pct=delta_red_full,
            ))

    scan_meta = {
        "scan_time_s": scan_elapsed,
        "modules": scan.get("module_count", 0),
        "files": scan.get("file_count", 0),
        "memory_tokens": mem_tokens,
        "memory_mode": mem_packet.get("mode", "SESSION"),
        "session_count": mem_packet.get("session_count", 1),
        "has_delta": mem_packet.get("has_delta", False),
    }
    return scan_meta, trials


def _aggregate(trials: List[TrialResult]) -> Dict[str, Any]:
    by_mode: Dict[str, List[TrialResult]] = {}
    for t in trials:
        by_mode.setdefault(t.export_mode, []).append(t)

    out: Dict[str, Any] = {}
    for mode, rows in by_mode.items():
        q_avg = statistics.mean(r.quality for r in rows)
        g_avg = statistics.mean(r.grounding for r in rows)
        tok_avg = statistics.mean(r.export_tokens for r in rows)
        hal_pct = 100 * sum(1 for r in rows if r.hallucinated_file) / len(rows)
        out[mode] = {
            "quality_avg": round(q_avg, 3),
            "grounding_avg": round(g_avg, 3),
            "export_tokens_avg": round(tok_avg, 1),
            "hallucination_pct": round(hal_pct, 1),
        }

    # Compute deltas (MEMORY vs MINIMAL, MINIMAL vs FULL)
    if atlas_export.FULL_EXPORT in out and atlas_export.MINIMAL_EXPORT in out:
        out["p169_token_reduction_pct"] = round(
            100 * (1 - out[atlas_export.MINIMAL_EXPORT]["export_tokens_avg"] /
                   out[atlas_export.FULL_EXPORT]["export_tokens_avg"]), 1
        )
        out["p169_quality_delta"] = round(
            out[atlas_export.MINIMAL_EXPORT]["quality_avg"] -
            out[atlas_export.FULL_EXPORT]["quality_avg"], 3
        )

    if atlas_export.MINIMAL_EXPORT in out and atlas_export.MEMORY_EXPORT in out:
        mem_tok = out[atlas_export.MEMORY_EXPORT]["export_tokens_avg"]
        min_tok = out[atlas_export.MINIMAL_EXPORT]["export_tokens_avg"]
        out["p172_delta_reduction_vs_minimal_pct"] = round(
            100 * (1 - mem_tok / min_tok) if min_tok else 0.0, 1
        )
        out["p172_quality_delta_vs_minimal"] = round(
            out[atlas_export.MEMORY_EXPORT]["quality_avg"] -
            out[atlas_export.MINIMAL_EXPORT]["quality_avg"], 3
        )
        out["p172_hallucination_delta_vs_minimal_ppt"] = round(
            out[atlas_export.MEMORY_EXPORT]["hallucination_pct"] -
            out[atlas_export.MINIMAL_EXPORT]["hallucination_pct"], 1
        )

    # Memory packet overhead
    mem_trials = by_mode.get(atlas_export.MEMORY_EXPORT, [])
    if mem_trials:
        out["memory_packet_tokens_avg"] = round(
            statistics.mean(r.memory_packet_tokens for r in mem_trials), 1
        )
        out["delta_tokens_avg"] = round(
            statistics.mean(r.delta_tokens for r in mem_trials if r.delta_tokens), 1
        )

    return out


def _passes_criteria(agg: Dict[str, Any]) -> Dict[str, bool]:
    return {
        # Phase 170 backward-compat bar
        "quality_delta_full_vs_minimal_lte_0_2": abs(agg.get("p169_quality_delta", 0.0)) <= 0.2,
        # Phase 172 memory bar
        "delta_reduction_vs_minimal_gte_50pct": agg.get("p172_delta_reduction_vs_minimal_pct", 0) >= 50.0,
        "memory_quality_delta_vs_minimal_gte_neg_0_2": agg.get("p172_quality_delta_vs_minimal", -999) >= -0.2,
        "hallucination_delta_vs_minimal_lte_0": agg.get("p172_hallucination_delta_vs_minimal_ppt", 1) <= 0.0,
        "memory_packet_tokens_lte_150": agg.get("memory_packet_tokens_avg", 999) <= 150,
    }


def main(repos: Optional[List[str]] = None) -> None:
    import tempfile

    target_repos = {k: v for k, v in REPOS.items() if repos is None or k in (repos or [])}
    available = {k: v for k, v in target_repos.items() if v["path"].is_dir()}

    if not available:
        print("[phase172] No external repos available. Abort.", flush=True)
        return

    data_dir = tempfile.mkdtemp(prefix="atlas_phase172_")
    print(f"[phase172] Memory data_dir: {data_dir}", flush=True)

    all_trials: List[TrialResult] = []
    scan_metas: Dict[str, Any] = {}

    for repo_id, meta in available.items():
        print(f"\n[phase172] Scanning {meta['label']}...", flush=True)
        scan_meta, trials = run_repo(repo_id, meta["path"], data_dir=data_dir)
        if trials:
            all_trials.extend(trials)
            scan_metas[f"scan_{repo_id}"] = scan_meta

    if not all_trials:
        print("[phase172] No trials produced. Abort.", flush=True)
        return

    agg = _aggregate(all_trials)
    passes = _passes_criteria(agg)
    all_pass = all(passes.values())

    # ---------- Print summary ----------
    print("\n" + "=" * 60, flush=True)
    print("[phase172] RESULTS", flush=True)
    print("=" * 60, flush=True)

    modes = [atlas_export.FULL_EXPORT, atlas_export.MINIMAL_EXPORT, atlas_export.MEMORY_EXPORT]
    header = f"{'Mode':<20} {'Tokens':>8} {'Quality':>8} {'Grounding':>10} {'Halluc%':>8}"
    print(header, flush=True)
    print("-" * 60, flush=True)
    for mode in modes:
        row = agg.get(mode, {})
        print(
            f"{mode:<20} {row.get('export_tokens_avg', 0):>8.1f} "
            f"{row.get('quality_avg', 0):>8.3f} "
            f"{row.get('grounding_avg', 0):>10.3f} "
            f"{row.get('hallucination_pct', 0):>8.1f}%",
            flush=True,
        )

    print("", flush=True)
    print(f"Phase 169 token reduction (MINIMAL vs FULL): "
          f"{agg.get('p169_token_reduction_pct', 0):.1f}%", flush=True)
    print(f"Phase 172 delta reduction (MEMORY vs MINIMAL): "
          f"{agg.get('p172_delta_reduction_vs_minimal_pct', 0):.1f}%", flush=True)
    print(f"Phase 172 quality delta vs MINIMAL: "
          f"{agg.get('p172_quality_delta_vs_minimal', 0):+.3f}", flush=True)
    print(f"Memory packet tokens avg: "
          f"{agg.get('memory_packet_tokens_avg', 0):.1f}", flush=True)
    print(f"Delta tokens avg: "
          f"{agg.get('delta_tokens_avg', 0):.1f}", flush=True)

    print("\nPass criteria:", flush=True)
    for criterion, passed in passes.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {criterion}", flush=True)
    print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}", flush=True)

    # ---------- Write output ----------
    REPORTS.mkdir(parents=True, exist_ok=True)
    raw = {
        "meta": {
            "phase": 172,
            "scoring_method": "export_grounded_proxy",
            "tasks_per_repo": len(BASE_TASKS),
            "modes": modes,
            "repos_scanned": list(available.keys()),
            **scan_metas,
        },
        "aggregate": agg,
        "passes": passes,
        "all_pass": all_pass,
        "trials": [asdict(t) for t in all_trials],
    }
    RAW_OUT.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    print(f"\n[phase172] Wrote {RAW_OUT.name}", flush=True)

    os.environ.pop("JARVIS_DESKTOP_DATA", None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 172 memory validation")
    parser.add_argument("--repos", nargs="+", help="Repo IDs to run (default: all)")
    args = parser.parse_args()
    main(repos=args.repos)
