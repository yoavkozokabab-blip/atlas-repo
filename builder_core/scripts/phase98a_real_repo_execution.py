"""Phase 98A real-repository validation execution (measurement only).

Assembles the Phase 95B 24-repository corpus, freezes commits, runs the
existing Phase 95A harness, and writes aggregate artifacts. No detector,
benchmark, or infrastructure changes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from builder_core.bug_intelligence import engine
from builder_core.real_repo_validation import harness

ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "data" / "real_repo_corpus" / "phase98a"
MANIFEST_PATH = ROOT / "reports" / "phase98a_manifest.json"
OUTPUT_DIR = ROOT / "reports" / "phase98a_run"
REPORT_PATH = ROOT / "reports" / "phase98a_real_repository_validation_execution.md"

# Preregistered public repositories (selected before scan per Phase 95B).
# (id, git_url, pin_ref, size_band, language_profile, project_shape, license, rationale)
CORPUS_SPEC: List[Tuple[str, str, str, str, str, str, str, str]] = [
    ("click", "https://github.com/pallets/click.git", "8.1.7", "small", "python_dominant", "cli tool", "BSD-3-Clause",
     "Maintained CLI composition library with flat layout and broad adoption."),
    ("itsdangerous", "https://github.com/pallets/itsdangerous.git", "2.2.0", "small", "python_dominant", "library", "BSD-3-Clause",
     "Small security helper library used across the Python ecosystem."),
    ("blinker", "https://github.com/pallets-eco/blinker.git", "1.9.0", "small", "python_dominant", "library", "MIT",
     "Signal/dispatch library with minimal surface area."),
    ("humanize", "https://github.com/python-humanize/humanize.git", "4.9.0", "small", "python_dominant", "library", "MIT",
     "Human-readable formatting helpers in a compact codebase."),
    ("cachetools", "https://github.com/tkem/cachetools.git", "5.3.3", "small", "python_dominant", "library", "MIT",
     "Caching utilities with clear API contracts."),
    ("pathspec", "https://github.com/cpburnz/python-pathspec.git", "0.12.1", "small", "python_dominant", "library", "MPL-2.0",
     "Path pattern matching library used by build tooling."),
    ("attrs", "https://github.com/python-attrs/attrs.git", "23.2.0", "small", "python_dominant", "library", "MIT",
     "Class decorator library with extensive tests."),
    ("pluggy", "https://github.com/pytest-dev/pluggy.git", "1.5.0", "small", "python_dominant", "library", "MIT",
     "Plugin hook library underpinning pytest."),
    ("requests", "https://github.com/psf/requests.git", "2.31.0", "medium", "python_dominant", "library", "Apache-2.0",
     "HTTP client library with real-world caller patterns."),
    ("httpx", "https://github.com/encode/httpx.git", "0.27.0", "medium", "python_dominant", "library", "BSD-3-Clause",
     "Modern async-capable HTTP client."),
    ("rich", "https://github.com/Textualize/rich.git", "13.7.1", "medium", "python_dominant", "library", "MIT",
     "Terminal formatting library with substantial API surface."),
    ("marshmallow", "https://github.com/marshmallow-code/marshmallow.git", "3.21.3", "medium", "python_dominant", "library", "MIT",
     "Serialization/validation library with schema patterns."),
    ("typer", "https://github.com/fastapi/typer.git", "0.12.3", "medium", "python_centered_polyglot", "cli tool", "MIT",
     "CLI builder layered on Click and type hints."),
    ("flask", "https://github.com/pallets/flask.git", "3.0.3", "medium", "python_centered_polyglot", "web application", "BSD-3-Clause",
     "Web microframework with templates and static assets alongside Python."),
    ("werkzeug", "https://github.com/pallets/werkzeug.git", "3.0.3", "medium", "python_centered_polyglot", "library", "BSD-3-Clause",
     "WSGI utilities with mixed template/static context."),
    ("cookiecutter", "https://github.com/cookiecutter/cookiecutter.git", "2.6.0", "medium", "python_secondary", "developer tool", "BSD-3-Clause",
     "Project templating tool with docs and templates alongside Python."),
    ("sphinx", "https://github.com/sphinx-doc/sphinx.git", "7.3.7", "medium", "python_secondary", "developer tool", "BSD-3-Clause",
     "Documentation generator with RST, templates, and JavaScript alongside Python."),
    ("dash", "https://github.com/plotly/dash.git", "2.17.0", "medium", "python_secondary", "web application", "MIT",
     "Plotly Dash with JavaScript and Python application layers."),
    ("starlette", "https://github.com/encode/starlette.git", "0.37.2", "large", "python_centered_polyglot", "web application", "BSD-3-Clause",
     "ASGI toolkit with routing and middleware patterns."),
    ("fastapi", "https://github.com/tiangolo/fastapi.git", "0.111.0", "large", "python_centered_polyglot", "web application", "MIT",
     "API framework combining Starlette and Pydantic."),
    ("pytest", "https://github.com/pytest-dev/pytest.git", "8.2.0", "large", "python_centered_polyglot", "developer tool", "MIT",
     "Test runner and plugin host with broad internal surface."),
    ("black", "https://github.com/psf/black.git", "24.4.2", "large", "python_centered_polyglot", "developer tool", "MIT",
     "Formatter with substantial AST and line-breaking logic."),
    ("celery", "https://github.com/celery/celery.git", "5.4.0", "large", "python_centered_polyglot", "automation system", "BSD-3-Clause",
     "Distributed task queue with docs and config alongside Python."),
    ("wagtail", "https://github.com/wagtail/wagtail.git", "6.1.0", "large", "python_secondary", "web application", "BSD-3-Clause",
     "CMS with Django templates, JavaScript, and SCSS alongside Python."),
]


def _git_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(args: List[str], *, cwd: Optional[str] = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_git_env(),
    )


def _run_cmd(args: List[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_git_env(),
    )


def _git(args: List[str], cwd: str, *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return _run_git(args, cwd=cwd, timeout=timeout)


def _git_out(args: List[str], cwd: str) -> Optional[str]:
    try:
        proc = _git(args, cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _resolve_tag(url: str, pin_ref: str) -> str:
    candidates = [pin_ref]
    if not pin_ref.startswith("v"):
        candidates.append(f"v{pin_ref}")
    for tag in candidates:
        proc = _run_git(["ls-remote", "--tags", url, tag], timeout=120)
        if proc.returncode == 0 and proc.stdout.strip():
            return tag
    proc = _run_git(["ls-remote", "--tags", url], timeout=120)
    if proc.returncode != 0:
        return pin_ref
    for line in proc.stdout.splitlines():
        ref = line.split("\t")[-1]
        bare = ref.removeprefix("refs/tags/").removesuffix("^{}")
        if bare == pin_ref or bare == f"v{pin_ref}":
            return bare
    return pin_ref


def _clone_or_checkout(repo_id: str, url: str, pin_ref: str) -> Path:
    resolved_ref = _resolve_tag(url, pin_ref)
    dest = CORPUS_ROOT / repo_id
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not (dest / ".git").is_dir():
        shutil.rmtree(dest)
    if not (dest / ".git").is_dir():
        shallow = _run_cmd(
            ["git", "clone", "--depth", "1", "--branch", resolved_ref, url, str(dest)],
            timeout=600,
        )
        if shallow.returncode != 0:
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            proc = _run_cmd(["git", "clone", url, str(dest)], timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(f"{repo_id}: clone failed: {proc.stderr.strip()}")
    _git(["config", "core.longpaths", "true"], str(dest))
    for fetch_ref in (f"tag:{resolved_ref}", resolved_ref, f"refs/tags/{resolved_ref}"):
        _git(["fetch", "--depth", "1", "origin", fetch_ref], str(dest))
    checkout = _git(["checkout", "--force", resolved_ref], str(dest))
    if checkout.returncode != 0:
        checkout = _git(["checkout", "--force", f"tags/{resolved_ref}"], str(dest))
    head = _git_out(["rev-parse", "HEAD"], str(dest))
    if not head:
        raise RuntimeError(
            f"{repo_id}: cannot checkout {resolved_ref}: {checkout.stderr.strip()}"
        )
    status = _git_out(["status", "--short"], str(dest))
    if status:
        raise RuntimeError(f"{repo_id}: checkout not clean after pin")
    return dest


def _python_stats(root: str) -> Tuple[int, int]:
    files = engine._collect_python_files(root)
    loc = 0
    for abs_path, _rel in files:
        try:
            loc += sum(1 for _ in open(abs_path, encoding="utf-8-sig", errors="ignore"))
        except OSError:
            continue
    return len(files), loc


def _measured_size_band(python_loc: int, python_files: int, planned: str) -> str:
    if python_loc <= 5000 and python_files <= 40:
        return "small"
    if python_loc <= 50000 and python_files <= 300:
        return "medium"
    if python_loc <= 250000 and python_files <= 1500:
        return "large"
    return "stress"


def assemble_manifest(skip_clone: bool = False) -> Dict[str, Any]:
    candidate = harness.candidate_record()
    repositories: List[Dict[str, Any]] = []
    replacements: List[Dict[str, Any]] = []

    for index, spec in enumerate(CORPUS_SPEC, start=1):
        repo_id, url, pin_ref, planned_band, lang, shape, license_, rationale = spec
        print(f"[{index}/{len(CORPUS_SPEC)}] {repo_id} @ {pin_ref}", flush=True)
        if skip_clone and not (CORPUS_ROOT / repo_id).is_dir():
            replacements.append({"id": repo_id, "reason": "missing checkout"})
            continue
        if not skip_clone:
            path = _clone_or_checkout(repo_id, url, pin_ref)
        else:
            path = CORPUS_ROOT / repo_id
        commit = _git_out(["rev-parse", "HEAD"], str(path))
        if not commit:
            raise RuntimeError(f"{repo_id}: cannot resolve HEAD")
        py_files, py_loc = _python_stats(str(path))
        measured_band = _measured_size_band(py_loc, py_files, planned_band)
        if measured_band == "stress":
            replacements.append({
                "id": repo_id,
                "reason": f"exceeds primary large band ({py_loc} LOC, {py_files} files)",
            })
        repositories.append({
            "id": repo_id,
            "path": str(path.resolve()),
            "commit": commit,
            "license": license_,
            "size_band": measured_band if measured_band != "stress" else "large",
            "language_profile": lang,
            "project_shape": shape,
            "python_files": py_files,
            "python_loc": py_loc,
            "selection_rationale": rationale,
            "track": "primary",
            "primary_eligible": measured_band != "stress",
            "eligibility_note": (
                "stress appendix candidate" if measured_band == "stress" else ""
            ),
            "pin_ref": pin_ref,
            "url": url,
        })

    manifest = {
        "schema_version": 1,
        "program_id": "phase98a-public-corpus-v1",
        "sampling_seed": "phase98a-public-corpus-v1",
        "candidate": candidate,
        "historical_bugs": [],
        "repositories": repositories,
        "replacement_log": replacements,
    }
    harness.write_json(MANIFEST_PATH, manifest)
    return manifest


def run_validation(manifest: Dict[str, Any]) -> Dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    program = harness.run_to_directory(manifest, OUTPUT_DIR)
    elapsed = round(time.perf_counter() - started, 3)
    metrics = harness.load_json(OUTPUT_DIR / "metrics.json")
    return {"program": program, "metrics": metrics, "elapsed_seconds": elapsed}


def _render_report(manifest: Dict[str, Any], result: Dict[str, Any]) -> str:
    program = result["program"]
    metrics = result["metrics"]
    inventory = metrics.get("finding_inventory", {})
    readiness = metrics.get("readiness", {})
    corpus = harness.corpus_summary(manifest, program)
    precision = metrics.get("precision", {})
    usefulness = metrics.get("usefulness", {})

    primary = [r for r in manifest["repositories"] if r.get("primary_eligible")]
    scans = {s["repo_id"]: s for s in program["scans"]}

    lines = [
        "# Phase 98A — Real Repository Validation Execution",
        "",
        "**Status:** Execution complete  ",
        "**Date:** 2026-05-31  ",
        "**Scope:** Full Phase 95 validation workflow — no detector, benchmark, or infrastructure changes  ",
        "**Artifacts:** `reports/phase98a_run/`",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"Phase 98A assembled and scanned **{len(manifest['repositories'])}** public repositories",
        f"from the Phase 95B corpus plan (**{len(primary)}** primary-eligible).",
        f"Commits were frozen at clone time; the harness ran read-only with",
        f"Builder Core `{manifest['candidate']['builder_core_commit'][:12]}…`.",
        "",
        f"**External-alpha verdict:** `{readiness.get('verdict', 'HOLD')}`",
        "",
        "Human review labels were **not** recorded in this execution pass.",
        "Strict precision and usefulness gates remain **unavailable** until review completes.",
        "",
        "---",
        "",
        "## Frozen candidate",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Builder Core commit | `{manifest['candidate']['builder_core_commit']}` |",
    ]
    for flag, value in sorted(manifest["candidate"]["frozen_flags"].items()):
        lines.append(f"| `{flag}` | `{value}` |")
    lines.extend([
        "",
        "---",
        "",
        "## Corpus composition",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Repositories in manifest | {corpus['repositories_scanned']} |",
        f"| Primary-eligible | {corpus['primary_eligible_repositories']} |",
        f"| Historical bug cases | {corpus['historical_bug_cases']} |",
        "",
        "### Size bands (manifest)",
        "",
    ])
    for band, count in sorted(corpus.get("size_bands", {}).items()):
        lines.append(f"- `{band}`: {count}")
    lines.extend([
        "",
        "### Scan outcomes",
        "",
        "| Outcome | Count |",
        "|---------|------:|",
    ])
    for outcome, count in sorted(corpus.get("outcomes", {}).items()):
        lines.append(f"| `{outcome}` | {count} |")

    lines.extend([
        "",
        "### Repository table",
        "",
        "| Repository | Commit | Band | Py files | Py LOC | Outcome | Duration (s) | Findings | Grounded |",
        "|------------|--------|------|---------:|-------:|---------|---------------:|---------:|---------:|",
    ])
    for repo in sorted(manifest["repositories"], key=lambda r: r["id"]):
        scan = scans.get(repo["id"], {})
        lines.append(
            f"| `{repo['id']}` | `{repo['commit'][:12]}` | {repo['size_band']} | "
            f"{repo.get('python_files', '?')} | {repo.get('python_loc', '?')} | "
            f"`{scan.get('outcome', 'n/a')}` | {scan.get('duration_seconds', 'n/a')} | "
            f"{len(scan.get('records', []))} | {scan.get('verdict_eligible_count', 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Finding inventory",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Total exported findings | {inventory.get('total_findings', 0)} |",
        f"| Verdict-eligible (grounded) | {inventory.get('verdict_eligible_findings', 0)} |",
        f"| Advisory (reported separately) | {inventory.get('advisory_findings', 0)} |",
        f"| Review sample size | {len(harness.load_json(OUTPUT_DIR / 'review_sample.json'))} |",
        "",
        "### Grounded findings by kind",
        "",
    ])
    for kind, count in (inventory.get("verdict_by_kind") or {}).items():
        lines.append(f"- `{kind}`: {count}")

    lines.extend([
        "",
        "---",
        "",
        "## Aggregate metrics (pre-review)",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Strict precision | {precision.get('strict_precision', 'unavailable')} |",
        f"| Misleading rate | {precision.get('misleading_rate', 'unavailable')} |",
        f"| Review-lead rate | {precision.get('review_lead_rate', 'unavailable')} |",
        f"| Unreviewed in sample | {precision.get('unreviewed', 'n/a')} |",
        f"| Mean finding usefulness | {usefulness.get('per_finding', {}).get('mean_usefulness', 'unavailable')} |",
        f"| Harness wall time (s) | {result['elapsed_seconds']} |",
        "",
        "---",
        "",
        "## Readiness gates",
        "",
        f"**Verdict:** `{readiness.get('verdict', 'HOLD')}`",
        "",
        "| Gate | Passed | Detail |",
        "|------|:------:|--------|",
    ])
    for gate in readiness.get("gates", []):
        lines.append(
            f"| {gate['name']} | {'yes' if gate['passed'] else 'no'} | {gate['detail']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Workflow artifacts",
        "",
        "Generated under `reports/phase98a_run/`:",
        "",
        "- `manifest.normalized.json`",
        "- `program.json`",
        "- `findings.json`",
        "- `review_sample.json`",
        "- `reviewer_a_packets.json` / `reviewer_b_packets.json` / `adjudication_packets.json`",
        "- `reviews.json` (unreviewed template)",
        "- `repository_scores.json`",
        "- `negative_file_sample.json`",
        "- `historical_bug_reviews.json`",
        "- `metrics.json`",
        "- `report.md`",
        "",
        "Preregistered manifest: `reports/phase98a_manifest.json`",
        "",
        "---",
        "",
        "## Constraints honored",
        "",
        "- No new detectors",
        "- No new facts infrastructure",
        "- No benchmark behavior changes",
        "- Target repositories not modified (read-only scan + external artifacts)",
        "",
        "---",
        "",
        "## Next steps (out of scope for 98A)",
        "",
        "1. Preregister 20–30 historical bug cases across ≥10 repositories.",
        "2. Complete blinded human review on exported packets.",
        "3. Re-run `cli report` after labeling to close precision/usefulness gates.",
    ])
    if manifest.get("replacement_log"):
        lines.extend([
            "",
            "### Replacement / eligibility notes",
            "",
        ])
        for item in manifest["replacement_log"]:
            lines.append(f"- `{item['id']}`: {item['reason']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 98A real-repo validation execution")
    parser.add_argument("--skip-clone", action="store_true", help="Use existing corpus checkouts")
    parser.add_argument("--manifest-only", action="store_true", help="Assemble manifest only")
    parser.add_argument("--report-only", action="store_true", help="Regenerate markdown report")
    args = parser.parse_args()

    if args.report_only:
        manifest = harness.load_json(MANIFEST_PATH)
        metrics = harness.load_json(OUTPUT_DIR / "metrics.json")
        program = harness.load_json(OUTPUT_DIR / "program.json")
        REPORT_PATH.write_text(
            _render_report(manifest, {"program": program, "metrics": metrics, "elapsed_seconds": "?"}),
            encoding="utf-8",
        )
        print(f"report: {REPORT_PATH}")
        return

    manifest = assemble_manifest(skip_clone=args.skip_clone)
    print(f"manifest: {MANIFEST_PATH} ({len(manifest['repositories'])} repos)")
    if args.manifest_only:
        return

    result = run_validation(manifest)
    REPORT_PATH.write_text(_render_report(manifest, result), encoding="utf-8")
    print(f"output: {OUTPUT_DIR}")
    print(f"report: {REPORT_PATH}")
    print(f"verdict: {result['metrics']['readiness']['verdict']}")


if __name__ == "__main__":
    main()
