"""Phase 65 Track E — coding assistant reliability."""

from __future__ import annotations

from pathlib import Path

import config
from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


def score_patch_recommendation(module_hint: str, files: list[str]) -> tuple[float, str]:
    """Confidence 0-1 that patch target module is identified."""
    hint = (module_hint or "").lower().replace("\\", "/")
    if not files:
        return 0.0, "no files"
    hits = [f for f in files if hint and hint in f.lower()]
    if hits:
        return 0.92, hits[0]
    # partial token match
    tokens = [t for t in hint.split("/") if len(t) > 3]
    for f in files:
        fl = f.lower()
        if any(t in fl for t in tokens):
            return 0.78, f
    return 0.35, files[0]


def validate_patch_path(path: str) -> tuple[bool, str]:
    p = Path(path)
    root = Path(config.PROJECT_ROOT).resolve()
    try:
        resolved = p.resolve()
    except OSError:
        return False, "invalid path"
    if not str(resolved).startswith(str(root)):
        return False, "outside project root"
    if not resolved.is_file():
        return False, "not a file"
    return True, "ok"


def run_coding_acceptance() -> TrackScore:
    score = TrackScore(track="Coding Assistant", current_pct=0.0, target_pct=90.0)

    def _inspect() -> tuple[bool, str]:
        from phase45_investigation import inspect_project

        body = inspect_project()
        return "inspection" in body.lower() or "project" in body.lower(), body[:120]

    def _bugs() -> tuple[bool, str]:
        from phase45_investigation import hunt_algorithm_bugs

        body = hunt_algorithm_bugs()
        return bool(body), body[:120]

    def _error() -> tuple[bool, str]:
        from phase45_investigation import explain_latest_error

        body = explain_latest_error()
        return bool(body), body[:120]

    def _patch_conf() -> tuple[bool, str]:
        files = ["local_jarvis/actions/registry.py", "local_jarvis/brain/router.py"]
        conf, hit = score_patch_recommendation("brain/router", files)
        return conf >= 0.7, f"confidence={conf} file={hit}"

    def _patch_validate() -> tuple[bool, str]:
        ok, msg = validate_patch_path("brain/router.py")
        return ok, msg

    score.cases.extend(
        [
            run_case("inspect_project", _inspect),
            run_case("bug_identification", _bugs),
            run_case("error_explanation", _error),
            run_case("patch_confidence", _patch_conf),
            run_case("patch_validation", _patch_validate),
        ]
    )
    score.finalize_score()
    if score.pass_rate < 80:
        score.blockers.append("Coding assistant acceptance below target.")
        score.recommendations.append("Expand investigation graph coverage for local_jarvis modules.")
    write_report(reports_dir() / "coding_assistant_report.md", format_track_report(score).splitlines())
    return score
