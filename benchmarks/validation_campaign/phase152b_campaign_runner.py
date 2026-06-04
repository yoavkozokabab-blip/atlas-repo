"""Phase 152B cross-repository validation campaign runner.

Measurement-only harness. It calls existing Atlas APIs and writes campaign
results/reports; it does not change Atlas intelligence or product behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "benchmarks" / "validation_campaign" / "results"
RUNTIME_DIR = ROOT / "benchmarks" / "validation_campaign" / "runtime_data"
REPORTS_DIR = ROOT / "reports"

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "coverage",
    ".gradle",
}
CODE_EXTS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".mjs",
    ".cjs",
    ".vue",
    ".svelte",
    ".kt",
    ".kts",
}

REPOS: List[Dict[str, Any]] = [
    {"id": "home_assistant", "name": "Home Assistant", "tier": 1, "language": "Python", "path": "external_repos/home_assistant", "url": "https://github.com/home-assistant/core.git", "concept": "event bus", "symptom": "why are duplicate events being fired", "build": "add rate limiting"},
    {"id": "django", "name": "Django", "tier": 1, "language": "Python", "path": "external_repos/django", "url": "https://github.com/django/django.git", "concept": "middleware", "symptom": "why are duplicate requests being handled", "build": "add distributed tracing"},
    {"id": "fastapi", "name": "FastAPI", "tier": 1, "language": "Python", "path": "external_repos/fastapi", "url": "https://github.com/fastapi/fastapi.git", "concept": "request validation", "symptom": "why are duplicate events being fired", "build": "add rate limiting"},
    {"id": "vscode", "name": "VS Code", "tier": 1, "language": "TypeScript", "path": "external_repos/vscode", "url": "https://github.com/microsoft/vscode.git", "concept": "extension host", "symptom": "why are duplicate commands being fired", "build": "add distributed tracing"},
    {"id": "atlas_self", "name": "Atlas self", "tier": 1, "language": "Python", "path": ".", "url": "local workspace", "concept": "impact engine", "symptom": "why are duplicate events being fired", "build": "add rate limiting"},
    {"id": "flask", "name": "Flask", "tier": 2, "language": "Python", "path": "external_repos/flask", "url": "https://github.com/pallets/flask.git", "concept": "routing", "symptom": "why are duplicate requests being handled", "build": "add rate limiting"},
    {"id": "requests", "name": "Requests", "tier": 2, "language": "Python", "path": "external_repos/requests", "url": "https://github.com/psf/requests.git", "concept": "session handling", "symptom": "why are duplicate retries happening", "build": "add distributed tracing"},
    {"id": "pydantic", "name": "Pydantic", "tier": 2, "language": "Python", "path": "external_repos/pydantic", "url": "https://github.com/pydantic/pydantic.git", "concept": "validation", "symptom": "why are duplicate validators firing", "build": "add rate limiting"},
    {"id": "rich", "name": "Rich", "tier": 2, "language": "Python", "path": "external_repos/rich", "url": "https://github.com/Textualize/rich.git", "concept": "console rendering", "symptom": "why are duplicate events being fired", "build": "add distributed tracing"},
    {"id": "typer", "name": "Typer", "tier": 2, "language": "Python", "path": "external_repos/typer", "url": "https://github.com/fastapi/typer.git", "concept": "command parsing", "symptom": "why are duplicate commands being fired", "build": "add rate limiting"},
    {"id": "celery", "name": "Celery", "tier": 2, "language": "Python", "path": "external_repos/celery", "url": "https://github.com/celery/celery.git", "concept": "task dispatch", "symptom": "why are duplicate tasks being fired", "build": "add distributed tracing"},
    {"id": "airflow", "name": "Airflow", "tier": 2, "language": "Python", "path": "external_repos/airflow", "url": "https://github.com/apache/airflow.git", "concept": "scheduler", "symptom": "why are duplicate tasks being fired", "build": "add distributed tracing"},
    {"id": "langchain", "name": "LangChain", "tier": 2, "language": "Python", "path": "external_repos/langchain", "url": "https://github.com/langchain-ai/langchain.git", "concept": "agent executor", "symptom": "why are duplicate tool calls happening", "build": "add distributed tracing"},
    {"id": "nextjs", "name": "Next.js", "tier": 3, "language": "TypeScript", "path": "external_repos/nextjs", "url": "https://github.com/vercel/next.js.git", "concept": "routing", "symptom": "why are duplicate requests being handled", "build": "add rate limiting"},
    {"id": "react", "name": "React", "tier": 3, "language": "TypeScript", "path": "external_repos/react", "url": "https://github.com/facebook/react.git", "concept": "scheduler", "symptom": "why are duplicate renders happening", "build": "add distributed tracing"},
    {"id": "nestjs", "name": "NestJS", "tier": 3, "language": "TypeScript", "path": "external_repos/nestjs", "url": "https://github.com/nestjs/nest.git", "concept": "dependency injector", "symptom": "why are duplicate requests being handled", "build": "add rate limiting"},
    {"id": "typeorm", "name": "TypeORM", "tier": 3, "language": "TypeScript", "path": "external_repos/typeorm", "url": "https://github.com/typeorm/typeorm.git", "concept": "repository pattern", "symptom": "why are duplicate queries being fired", "build": "add distributed tracing"},
    {"id": "turborepo", "name": "Turborepo", "tier": 3, "language": "TypeScript", "path": "external_repos/turborepo", "url": "https://github.com/vercel/turborepo.git", "concept": "task pipeline", "symptom": "why are duplicate tasks being fired", "build": "add distributed tracing"},
    {"id": "kubernetes", "name": "Kubernetes", "tier": 4, "language": "Go", "path": "external_repos/kubernetes", "url": "https://github.com/kubernetes/kubernetes.git", "concept": "scheduler", "symptom": "why are duplicate events being fired", "build": "add distributed tracing"},
    {"id": "qdrant", "name": "Qdrant", "tier": 4, "language": "Rust", "path": "external_repos/qdrant", "url": "https://github.com/qdrant/qdrant.git", "concept": "storage engine", "symptom": "why are duplicate writes happening", "build": "add rate limiting"},
    {"id": "spring_boot_example", "name": "Spring Boot example", "tier": 4, "language": "Java", "path": "external_repos/spring_boot_example", "url": "https://github.com/spring-projects/spring-petclinic.git", "concept": "controller routing", "symptom": "why are duplicate requests being handled", "build": "add rate limiting"},
    {"id": "aspnet_example", "name": "ASP.NET example", "tier": 4, "language": "C#", "path": "external_repos/aspnet_example", "url": "https://github.com/dotnet-architecture/eShopOnWeb.git", "concept": "request pipeline", "symptom": "why are duplicate orders being created", "build": "add distributed tracing"},
    {"id": "gin", "name": "Gin", "tier": 4, "language": "Go", "path": "external_repos/gin", "url": "https://github.com/gin-gonic/gin.git", "concept": "middleware", "symptom": "why are duplicate requests being handled", "build": "add rate limiting"},
]


def repo_path(spec: Dict[str, Any]) -> Path:
    return ROOT if spec["path"] == "." else (ROOT / spec["path"]).resolve()


def git_commit(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).strip()
    except Exception:
        return None


def repo_size(path: Path) -> Dict[str, Any]:
    files = code_files = loc = chars = 0
    for root, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            files += 1
            file_path = Path(root) / name
            if file_path.suffix.lower() not in CODE_EXTS:
                continue
            code_files += 1
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            chars += len(text)
            loc += text.count("\n") + (1 if text else 0)
    return {
        "total_files_on_disk": files,
        "code_files_counted": code_files,
        "code_loc": loc,
        "code_chars": chars,
        "source_token_estimate": int(chars / 4),
    }


def timed(fn):
    started = time.perf_counter()
    result = fn()
    return result, round(time.perf_counter() - started, 3)


def pct_reduction(raw: int, compact: int) -> float:
    if raw <= 0:
        return 0.0
    return round(max(0.0, (raw - compact) / raw * 100.0), 2)


def quality_understanding(scan: Dict[str, Any], graph: Dict[str, Any]) -> int:
    modules = int(scan.get("module_count") or 0)
    edges = int(scan.get("dependency_edges") or 0)
    subsystems = int(scan.get("subsystem_count") or 0)
    score = 0
    if modules > 0:
        score += 25
    if modules > 50:
        score += 20
    if modules > 500:
        score += 15
    if edges > 0:
        score += 15
    if edges > modules:
        score += 10
    if subsystems >= 3:
        score += 10
    if len(graph.get("nodes") or []) > 1:
        score += 10
    if scan.get("degraded"):
        score -= 15
    if (scan.get("unresolved_ratio") or 0) > 0.8:
        score -= 15
    if (scan.get("graph_build") or {}).get("partial"):
        score -= 10
    return max(0, min(100, score))


def quality_impact(response: Dict[str, Any]) -> int:
    blob = json.dumps(response, default=str).lower()
    if not response.get("ok") or "target not in graph" in blob:
        return 20 if response.get("ok") else 0
    score = 35
    if response.get("direct_impact") or response.get("indirect_impact") or response.get("affected_files"):
        score += 30
    if response.get("evidence"):
        score += 15
    if response.get("confidence") or response.get("confidence_explanation"):
        score += 10
    if response.get("recommended_verification"):
        score += 10
    return min(100, score)


def quality_investigation(response: Dict[str, Any]) -> int:
    if not response.get("ok"):
        return 0
    plan = response.get("plan") or {}
    score = 35
    if plan.get("hypotheses"):
        score += 25
    if plan.get("most_likely_root_cause"):
        score += 15
    if plan.get("verification_checklist"):
        score += 15
    blob = json.dumps(plan, default=str).lower()
    if ".prettierrc" in blob or "package.json" in blob or "pyproject.toml" in blob:
        score -= 20
    return max(0, min(100, score))


def quality_build(response: Dict[str, Any]) -> int:
    if not response.get("ok"):
        return 0
    plan = response.get("plan") or {}
    score = 30
    if plan.get("likely_affected_modules") or plan.get("likely_affected_subsystems"):
        score += 25
    if plan.get("implementation_order"):
        score += 20
    if plan.get("tests_required") or plan.get("tests_likely_affected"):
        score += 15
    if plan.get("rollback_plan"):
        score += 10
    return min(100, score)


def failure_taxonomy(record: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    status = record.get("status")
    scan = record.get("scan_metrics") or {}
    quality = record.get("quality") or {}
    reliability = record.get("reliability") or {}
    modules = scan.get("modules") or 0
    if status == "timeout":
        out.append("scan_timeout")
    if status not in {"measured", "ok"}:
        out.append("graph_failure")
    if modules == 0 and status in {"measured", "ok"}:
        out.append("graph_failure")
    if modules <= 1 and status in {"measured", "ok"}:
        out.append("language_support_gap")
    if scan.get("partial_graph") or reliability.get("partial_graph"):
        out.append("partial_graph")
    if (scan.get("unresolved_ratio") or 0) > 0.8:
        out.append("unresolved_import_explosion")
    if quality.get("impact_score", 0) < 50:
        out.append("impact_failure")
    if quality.get("investigation_score", 0) < 50:
        out.append("investigation_failure")
    if quality.get("build_plan_score", 0) < 50:
        out.append("build_plan_failure")
    return sorted(set(out)) or ["none"]


def reset_api_state(api) -> None:
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "architecture": None,
            "scan_cache": {},
        }
    )


def run_worker(spec: Dict[str, Any], out_path: Path) -> None:
    os.chdir(ROOT)
    os.environ["JARVIS_DESKTOP_DATA"] = str(RUNTIME_DIR / spec["id"])
    sys.path.insert(0, str(ROOT))

    from jarvis_desktop import api

    path = repo_path(spec)
    size = repo_size(path) if path.exists() else {}
    base: Dict[str, Any] = {
        "repo_id": spec["id"],
        "name": spec["name"],
        "tier": spec["tier"],
        "language": spec["language"],
        "path": str(path),
        "url": spec["url"],
        "commit": git_commit(path) if path.exists() else None,
        "measurement_source": "phase152b_live",
    }
    if not path.exists():
        base.update({"status": "unavailable", "errors": ["repository unavailable after clone attempt"]})
        out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
        return

    try:
        reset_api_state(api)
        scan, scan_duration = timed(lambda: api.scan_repository(str(path)))
        if not scan.get("ok"):
            base.update({"status": "scan_failed", "repo_size": size, "errors": [str(scan.get("error"))]})
            out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
            return

        graph, graph_duration = timed(lambda: api.current_graph("module"))
        _summary, _summary_duration = timed(api.current_summary)
        impact, impact_duration = timed(lambda: api.change_impact_simulation(spec["concept"]))
        investigation, investigation_duration = timed(lambda: api.investigate_symptom(spec["symptom"]))
        build, build_duration = timed(lambda: api.plan_change(spec["build"]))
        compact, compact_duration = timed(lambda: api.context_export("claude", "compact"))

        compact_tokens = int(compact.get("estimated_tokens") or max(1, len(compact.get("text") or "") // 4))
        raw_tokens = int(size.get("source_token_estimate") or 0)
        u_score = quality_understanding(scan, graph)
        i_score = quality_impact(impact)
        inv_score = quality_investigation(investigation)
        b_score = quality_build(build)
        overall = round(u_score * 0.25 + i_score * 0.30 + inv_score * 0.25 + b_score * 0.20, 2)
        graph_health = scan.get("graph_health")
        if isinstance(graph_health, dict):
            graph_health = graph_health.get("label") or graph_health.get("status")

        record = {
            **base,
            "status": "measured",
            "repo_size": size,
            "scan_metrics": {
                "files": scan.get("file_count"),
                "loc": size.get("code_loc"),
                "modules": scan.get("module_count"),
                "edges": scan.get("dependency_edges"),
                "subsystems": scan.get("subsystem_count"),
                "cycles": scan.get("import_cycle_count"),
                "unresolved_imports": scan.get("unresolved_imports"),
                "unresolved_ratio": scan.get("unresolved_ratio"),
                "graph_health": graph_health,
                "degraded_status": scan.get("degraded"),
                "partial_graph": (scan.get("graph_build") or {}).get("partial"),
            },
            "performance": {
                "scan_duration_sec": scan_duration,
                "graph_build_duration_sec": (scan.get("graph_build") or {}).get("elapsed_sec") or graph_duration,
                "evidence_build_duration_sec": (scan.get("evidence_build") or {}).get("elapsed_sec"),
                "impact_duration_sec": impact_duration,
                "investigation_duration_sec": investigation_duration,
                "build_plan_duration_sec": build_duration,
                "compact_export_duration_sec": compact_duration,
            },
            "quality": {
                "repository_understanding_score": u_score,
                "impact_score": i_score,
                "investigation_score": inv_score,
                "build_plan_score": b_score,
                "overall_score": overall,
            },
            "context_economics": {
                "raw_repository_token_estimate": raw_tokens,
                "atlas_compact_context_token_estimate": compact_tokens,
                "token_reduction_pct": pct_reduction(raw_tokens, compact_tokens),
                "estimated_tokens_avoided": max(0, raw_tokens - compact_tokens),
            },
            "reliability": {
                "scan_success": True,
                "retry_count": 0,
                "timeout": False,
                "zero_module_scan": not bool(scan.get("module_count")),
                "partial_graph": bool((scan.get("graph_build") or {}).get("partial")),
                "memory_pressure_warning": False,
            },
            "sample_outputs": {
                "impact_ok": impact.get("ok"),
                "impact_target": impact.get("target"),
                "impact_confidence": impact.get("confidence"),
                "investigation_ok": investigation.get("ok"),
                "build_plan_ok": build.get("ok"),
            },
            "errors": [],
        }
    except Exception as exc:
        record = {**base, "status": "scan_failed", "repo_size": size, "errors": [f"{type(exc).__name__}: {exc}"]}

    record["failure_taxonomy"] = failure_taxonomy(record)
    out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")


def normalize_overnight(raw: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    scan = raw.get("scan_metrics") or {}
    times = raw.get("time_metrics") or {}
    quality = raw.get("quality_metrics") or {}
    tokens = raw.get("token_economics") or {}
    size = raw.get("repo_size") or {}
    status = "timeout" if raw.get("status") == "timeout" else ("measured" if raw.get("status") == "measured" else str(raw.get("status") or "unknown"))
    compact_tokens = int(tokens.get("atlas_compact_tokens_est") or tokens.get("with_atlas_required_context_tokens_est") or 0)
    raw_tokens = int(size.get("source_token_estimate") or 0)
    record = {
        "repo_id": spec["id"],
        "name": spec["name"],
        "tier": spec["tier"],
        "language": spec["language"],
        "path": str(repo_path(spec)),
        "url": spec["url"],
        "commit": raw.get("commit"),
        "status": status,
        "measurement_source": "overnight_validation_existing_2026-06-04",
        "repo_size": size,
        "scan_metrics": {
            "files": scan.get("files"),
            "loc": scan.get("loc"),
            "modules": scan.get("modules"),
            "edges": scan.get("edges"),
            "subsystems": scan.get("subsystems"),
            "cycles": scan.get("cycles"),
            "unresolved_imports": scan.get("unresolved_imports"),
            "unresolved_ratio": scan.get("unresolved_ratio"),
            "graph_health": scan.get("graph_health_label"),
            "degraded_status": raw.get("status") != "measured",
            "partial_graph": raw.get("status") == "timeout",
        },
        "performance": {
            "scan_duration_sec": times.get("scan_duration_sec"),
            "graph_build_duration_sec": times.get("repository_map_duration_sec"),
            "evidence_build_duration_sec": times.get("evidence_build_duration_sec"),
            "impact_duration_sec": times.get("impact_duration_sec"),
            "investigation_duration_sec": times.get("investigation_duration_sec"),
            "build_plan_duration_sec": times.get("build_plan_duration_sec"),
            "compact_export_duration_sec": times.get("compact_export_duration_sec"),
        },
        "quality": {
            "repository_understanding_score": quality.get("understanding_score", 0),
            "impact_score": quality.get("impact_score", 0),
            "investigation_score": quality.get("investigation_score", 0),
            "build_plan_score": quality.get("build_score", 0),
            "overall_score": quality.get("overall_score", 0),
        },
        "context_economics": {
            "raw_repository_token_estimate": raw_tokens,
            "atlas_compact_context_token_estimate": compact_tokens,
            "token_reduction_pct": pct_reduction(raw_tokens, compact_tokens),
            "estimated_tokens_avoided": max(0, raw_tokens - compact_tokens),
        },
        "reliability": {
            "scan_success": raw.get("status") == "measured",
            "retry_count": 0,
            "timeout": raw.get("status") == "timeout",
            "zero_module_scan": not bool(scan.get("modules")),
            "partial_graph": raw.get("status") == "timeout",
            "memory_pressure_warning": False,
        },
        "errors": raw.get("errors") or [],
    }
    record["failure_taxonomy"] = failure_taxonomy(record)
    return record


def load_overnight() -> Dict[str, Any]:
    path = ROOT / "benchmarks" / "overnight_validation" / "aggregate_results.json"
    if not path.exists():
        return {}
    aggregate = json.loads(path.read_text(encoding="utf-8"))
    return {record.get("repo_id"): record for record in aggregate.get("results", [])}


def timeout_record(spec: Dict[str, Any], timeout_sec: int) -> Dict[str, Any]:
    path = repo_path(spec)
    size = repo_size(path) if path.exists() else {}
    record = {
        "repo_id": spec["id"],
        "name": spec["name"],
        "tier": spec["tier"],
        "language": spec["language"],
        "path": str(path),
        "url": spec["url"],
        "commit": git_commit(path) if path.exists() else None,
        "status": "timeout",
        "measurement_source": "phase152b_live",
        "repo_size": size,
        "scan_metrics": {
            "files": size.get("total_files_on_disk"),
            "loc": size.get("code_loc"),
            "modules": 0,
            "edges": 0,
            "subsystems": 0,
            "cycles": 0,
            "unresolved_imports": None,
            "graph_health": "timeout",
            "degraded_status": True,
            "partial_graph": True,
        },
        "performance": {"scan_duration_sec": timeout_sec},
        "quality": {
            "repository_understanding_score": 0,
            "impact_score": 0,
            "investigation_score": 0,
            "build_plan_score": 0,
            "overall_score": 0,
        },
        "context_economics": {
            "raw_repository_token_estimate": size.get("source_token_estimate", 0),
            "atlas_compact_context_token_estimate": 0,
            "token_reduction_pct": 0.0,
            "estimated_tokens_avoided": 0,
        },
        "reliability": {
            "scan_success": False,
            "retry_count": 0,
            "timeout": True,
            "zero_module_scan": True,
            "partial_graph": True,
            "memory_pressure_warning": False,
        },
        "errors": [f"timeout after {timeout_sec}s"],
    }
    record["failure_taxonomy"] = failure_taxonomy(record)
    return record


def run_campaign(timeout_sec: int, live_all: bool = False) -> List[Dict[str, Any]]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    overnight = load_overnight()
    results: List[Dict[str, Any]] = []
    for spec in REPOS:
        out_path = RESULTS_DIR / f"{spec['id']}.json"
        if not live_all and spec["id"] in overnight:
            record = normalize_overnight(overnight[spec["id"]], spec)
            out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            print(f"[phase152b] {spec['id']}: reused {record['status']}", flush=True)
        else:
            path = repo_path(spec)
            if not path.exists():
                record = {
                    "repo_id": spec["id"],
                    "name": spec["name"],
                    "tier": spec["tier"],
                    "language": spec["language"],
                    "path": str(path),
                    "url": spec["url"],
                    "status": "unavailable",
                    "measurement_source": "phase152b_live",
                    "errors": ["repository unavailable after clone attempt"],
                }
                record["failure_taxonomy"] = failure_taxonomy(record)
                out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            else:
                print(f"[phase152b] {spec['id']}: live timeout={timeout_sec}s", flush=True)
                try:
                    subprocess.run(
                        [sys.executable, __file__, "--worker", spec["id"], str(out_path)],
                        cwd=str(ROOT),
                        timeout=timeout_sec,
                        check=False,
                    )
                    record = json.loads(out_path.read_text(encoding="utf-8"))
                    if "failure_taxonomy" not in record:
                        record["failure_taxonomy"] = failure_taxonomy(record)
                        out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
                    print(f"[phase152b] {spec['id']}: {record.get('status')} score={(record.get('quality') or {}).get('overall_score')}", flush=True)
                except subprocess.TimeoutExpired:
                    record = timeout_record(spec, timeout_sec)
                    out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
                    print(f"[phase152b] {spec['id']}: timeout", flush=True)
        results.append(json.loads(out_path.read_text(encoding="utf-8")))
    return results


def md_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def avg(values: Iterable[Any]) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(nums) / len(nums), 2) if nums else 0.0


def write_reports(results: List[Dict[str, Any]], timeout_sec: int) -> None:
    aggregate = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "repo_timeout_sec": timeout_sec, "results": results}
    (ROOT / "benchmarks" / "validation_campaign" / "aggregate_results.json").write_text(
        json.dumps(aggregate, indent=2, default=str),
        encoding="utf-8",
    )
    completed = [record for record in results if record.get("status") == "measured"]
    attempted = len(results)

    leaderboard_rows = []
    for record in sorted(results, key=lambda item: ((item.get("quality") or {}).get("overall_score") or -1), reverse=True):
        scan = record.get("scan_metrics") or {}
        quality = record.get("quality") or {}
        leaderboard_rows.append(
            [
                record["repo_id"],
                record["language"],
                record.get("status"),
                quality.get("overall_score", 0),
                scan.get("modules"),
                scan.get("edges"),
                scan.get("subsystems"),
                scan.get("graph_health"),
                ", ".join(record.get("failure_taxonomy") or []),
            ]
        )
    (REPORTS_DIR / "phase152b_validation_leaderboard.md").write_text(
        "# Phase 152B Validation Leaderboard\n\n"
        + md_table(["Repo", "Language", "Status", "Overall", "Modules", "Edges", "Subsystems", "Graph health", "Failure taxonomy"], leaderboard_rows)
        + "\n",
        encoding="utf-8",
    )

    token_records = [record for record in results if (record.get("context_economics") or {}).get("atlas_compact_context_token_estimate")]
    token_rows = []
    for record in sorted(results, key=lambda item: ((item.get("context_economics") or {}).get("token_reduction_pct") or -1), reverse=True):
        economics = record.get("context_economics") or {}
        token_rows.append(
            [
                record["repo_id"],
                economics.get("raw_repository_token_estimate", 0),
                economics.get("atlas_compact_context_token_estimate", 0),
                economics.get("token_reduction_pct", 0),
                economics.get("estimated_tokens_avoided", 0),
                record.get("measurement_source"),
            ]
        )
    (REPORTS_DIR / "phase152b_token_economics.md").write_text(
        "# Phase 152B Token Economics\n\n"
        + f"Repositories with compact context evidence: {len(token_records)} / {attempted}.\n\n"
        + f"Average token reduction: {avg((record.get('context_economics') or {}).get('token_reduction_pct') for record in token_records)}%.\n\n"
        + md_table(["Repo", "Raw repo tokens", "Atlas compact tokens", "Reduction %", "Tokens avoided", "Source"], token_rows)
        + "\n",
        encoding="utf-8",
    )

    failure_counts: Counter[str] = Counter()
    repos_by_failure: Dict[str, List[str]] = defaultdict(list)
    for record in results:
        for failure in record.get("failure_taxonomy") or []:
            if failure == "none":
                continue
            failure_counts[failure] += 1
            repos_by_failure[failure].append(record["repo_id"])
    failure_rows = [[failure, count, ", ".join(repos_by_failure[failure])] for failure, count in failure_counts.most_common()]
    (REPORTS_DIR / "phase152b_failure_taxonomy.md").write_text(
        "# Phase 152B Failure Taxonomy\n\n"
        + md_table(["Failure", "Frequency", "Affected repositories"], failure_rows or [["none", 0, ""]])
        + "\n",
        encoding="utf-8",
    )

    reliability_rows = []
    for record in results:
        reliability = record.get("reliability") or {}
        scan = record.get("scan_metrics") or {}
        performance = record.get("performance") or {}
        reliability_rows.append(
            [
                record["repo_id"],
                record.get("status"),
                reliability.get("scan_success"),
                reliability.get("timeout"),
                reliability.get("zero_module_scan"),
                reliability.get("partial_graph"),
                scan.get("degraded_status"),
                performance.get("scan_duration_sec"),
            ]
        )
    (REPORTS_DIR / "phase152b_reliability_summary.md").write_text(
        "# Phase 152B Reliability Summary\n\n"
        + f"Attempted: {attempted}\n\n"
        + f"Completed measured scans: {len(completed)}\n\n"
        + f"Timeouts: {sum(1 for record in results if (record.get('reliability') or {}).get('timeout'))}\n\n"
        + md_table(["Repo", "Status", "Scan success", "Timeout", "Zero modules", "Partial graph", "Degraded", "Scan sec"], reliability_rows)
        + "\n\nMeasurement caveat: an access-denied Python process tree from an interrupted prior test run was still visible before this campaign; timing should be treated as conservative/noisy if CPU contention occurred.\n",
        encoding="utf-8",
    )

    claim_lines = [
        "# Phase 152B Marketing Claims (Evidence-Backed Only)",
        "",
        f"- Atlas validation evidence covers {attempted} requested repositories across Python, TypeScript/JavaScript, Go, Rust, Java, and C# example codebases.",
        f"- {len(completed)} repositories produced measured scan results; {sum(1 for record in results if record.get('status') == 'timeout')} timed out or remained partial.",
    ]
    if token_records:
        best = max(token_records, key=lambda record: (record.get("context_economics") or {}).get("token_reduction_pct") or 0)
        claim_lines.append(
            f"- Across {len(token_records)} repositories with compact context evidence, Atlas reduced estimated AI context by an average of "
            f"{avg((record.get('context_economics') or {}).get('token_reduction_pct') for record in token_records)}% versus raw repository source tokens."
        )
        claim_lines.append(f"- Best observed rounded context reduction: {best['repo_id']} at {(best.get('context_economics') or {}).get('token_reduction_pct')}%.")
        claim_lines.append("- Token numbers are estimates based on source text length and compact packet size; rounded 100.0% rows are not literal zero-context claims.")
    claim_lines.extend(
        [
            "- Do not claim Atlas understands every codebase; failures and partial graphs are explicitly reported in the taxonomy.",
            "- Do not claim zero failures; timeout, partial graph, language support, and unresolved import risks remain visible.",
        ]
    )
    (REPORTS_DIR / "phase152b_marketing_claims.md").write_text("\n".join(claim_lines) + "\n", encoding="utf-8")

    by_language: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in results:
        by_language[record.get("language") or "unknown"].append(record)
    cross_language_rows = []
    for language, group in sorted(by_language.items()):
        cross_language_rows.append(
            [
                language,
                len(group),
                sum(1 for record in group if record.get("status") == "measured"),
                avg((record.get("quality") or {}).get("overall_score") for record in group),
                avg((record.get("scan_metrics") or {}).get("modules") for record in group),
                avg((record.get("scan_metrics") or {}).get("edges") for record in group),
            ]
        )
    best = sorted(results, key=lambda record: (record.get("quality") or {}).get("overall_score") or -1, reverse=True)[:5]
    worst = sorted(results, key=lambda record: (record.get("quality") or {}).get("overall_score") or 999)[:5]
    final_lines = [
        "# Phase 152B Cross-Repository Validation Campaign",
        "",
        f"Generated: {aggregate['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Repositories attempted: {attempted}",
        f"- Completed measured scans: {len(completed)}",
        "- Result directory: benchmarks/validation_campaign/results/",
        f"- Per-repo timeout for new live scans: {timeout_sec}s",
        "",
        "## Best Results",
        "",
        md_table(
            ["Repo", "Language", "Overall", "Modules", "Edges"],
            [[record["repo_id"], record["language"], (record.get("quality") or {}).get("overall_score"), (record.get("scan_metrics") or {}).get("modules"), (record.get("scan_metrics") or {}).get("edges")] for record in best],
        ),
        "",
        "## Worst Results",
        "",
        md_table(
            ["Repo", "Language", "Status", "Overall", "Failures"],
            [[record["repo_id"], record["language"], record.get("status"), (record.get("quality") or {}).get("overall_score"), ", ".join(record.get("failure_taxonomy") or [])] for record in worst],
        ),
        "",
        "## Cross-Language Performance",
        "",
        md_table(["Language", "Repos", "Measured", "Avg overall", "Avg modules", "Avg edges"], cross_language_rows),
        "",
        "## Biggest Limitations",
        "",
    ]
    for failure, count in failure_counts.most_common(8):
        final_lines.append(f"- {failure}: {count} repo(s) - {', '.join(repos_by_failure[failure])}")
    final_lines.extend(
        [
            "",
            "## Recommended Next Engineering Priorities",
            "",
            "- Improve non-Python/TypeScript graph extraction where language_support_gap appears.",
            "- Reduce unresolved import explosions before making stronger impact-analysis claims.",
            "- Add scan timeout/degraded-result UX so large repos produce useful partial evidence instead of silent long waits.",
            "- Separate centrality, risk, and partial-coverage confidence in benchmark-facing reports.",
            "- Re-run live scans on overnight-reused repositories when a full unattended window is available.",
            "",
            "## Measurement Notes",
            "",
            "- This campaign did not modify Atlas intelligence or product code.",
            "- Existing overnight evidence from 2026-06-04 was reused for repositories already measured there; newly cloned Phase 152B additions were measured live.",
            "- Marketing claims are limited to the measured evidence above.",
        ]
    )
    (REPORTS_DIR / "phase152b_cross_repository_validation.md").write_text("\n".join(final_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", help="Run a single repository worker by repo id.")
    parser.add_argument("worker_output", nargs="?")
    parser.add_argument("--timeout-sec", type=int, default=int(os.environ.get("PHASE152B_REPO_TIMEOUT", "420")))
    parser.add_argument("--live-all", action="store_true", help="Ignore existing overnight evidence and run every repo live.")
    args = parser.parse_args()

    if args.worker:
        spec = next(item for item in REPOS if item["id"] == args.worker)
        if not args.worker_output:
            raise SystemExit("worker output path required")
        run_worker(spec, Path(args.worker_output))
        return 0

    results = run_campaign(args.timeout_sec, live_all=args.live_all)
    write_reports(results, args.timeout_sec)
    measured = sum(1 for record in results if record.get("status") == "measured")
    timeouts = sum(1 for record in results if (record.get("reliability") or {}).get("timeout"))
    print(json.dumps({"attempted": len(results), "measured": measured, "timeouts": timeouts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
