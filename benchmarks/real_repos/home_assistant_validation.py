"""Phase 133/133B — Real-repository validation on Home Assistant.

Validates that Atlas indexes and understands a large real-world repository
(~26k files, ~9.7k production Python modules), not just the synthetic reference.

Run directly:
    py -3 benchmarks/real_repos/home_assistant_validation.py

Or via pytest (opt-in, slow ~2 min cold scan):
    set ATLAS_RUN_HA=1 && py -3 -m pytest benchmarks/real_repos/home_assistant_validation.py -q

The HA checkout is expected at external_repos/home_assistant (override with
ATLAS_HA_REPO). Conceptual-area correctness is validated, never a single file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HA_REPO = Path(os.environ.get("ATLAS_HA_REPO", str(ROOT / "external_repos" / "home_assistant")))


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").lower()


def _any_contains(items: List[str], needles: Tuple[str, ...]) -> bool:
    blob = " ".join(_norm(i) for i in items)
    return any(n in blob for n in needles)


def scan() -> Dict[str, Any]:
    from atlas_desktop import api

    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "scan_cache": {}})
    return api.scan_repository(str(HA_REPO))


def validate(verbose: bool = True) -> Dict[str, Any]:
    from atlas_desktop import api

    results: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))
        if verbose:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    s = scan()
    g = api._STATE.get("graph") or {}
    module_paths = [n.get("path") or "" for n in g.get("nodes", []) if n.get("type") == "module"]

    # ---- Repository Map ----
    modules = int(s.get("module_count") or 0)
    edges = int(s.get("dependency_edges") or 0)
    check("repository_map.modules>5000", modules > 5000, f"modules={modules}")
    check("repository_map.edges>10000", edges > 10000, f"edges={edges}")
    ha_areas = ("homeassistant/components", "homeassistant/auth", "homeassistant/helpers",
                "homeassistant/core.py", "homeassistant/config_entries.py",
                "homeassistant/components/recorder")
    for area in ha_areas:
        check(f"repository_map.has[{area}]", _any_contains(module_paths, (area,)))
    check("repository_map.not_collapsed", modules > 1, f"modules={modules}")

    # ---- Impact: semantic targets ----
    def impact_area(target: str, needles: Tuple[str, ...]) -> None:
        r = api.change_impact_simulation(target)
        found = (r.get("affected_files") or []) + ([r.get("target")] if r.get("target") else [])
        ok = bool(r.get("ok")) and not r.get("mock") and _any_contains(found, needles)
        check(f"impact[{target}]", ok, f"target={r.get('target')!r} mock={r.get('mock')}")

    impact_area("remove websocket support", ("websocket",))
    impact_area("remove the event bus", ("core.py", "event"))
    impact_area("remove authentication", ("auth",))

    # ---- Investigation: runtime symptoms never route to dotfiles ----
    def inv_check(symptom: str, expect: Tuple[str, ...]) -> None:
        r = api.investigate_symptom(symptom)
        mods = r.get("plan", {}).get("likely_modules") or []
        no_dotfiles = not _any_contains(mods, ("prettier", "package.json", "pyproject", ".lock", "eslint"))
        on_area = _any_contains(mods, expect)
        check(f"investigate[{symptom}].no_dotfiles", no_dotfiles, f"top={mods[:3]}")
        check(f"investigate[{symptom}].on_area", on_area, f"top={mods[:3]}")

    inv_check("why are duplicate events being fired", ("core.py", "event", "automation", "dispatcher"))
    inv_check("websocket keeps disconnecting", ("websocket", "auth", "http"))
    inv_check("integrations loading slowly", ("config_entries", "setup", "loader", "bootstrap", "components"))

    # ---- Build planning: concept localization ----
    def build_check(req: str, expect: Tuple[str, ...]) -> None:
        r = api.plan_change(req)
        mods = (r.get("plan", {}).get("likely_affected_modules") or []) + \
               (r.get("plan", {}).get("files_to_inspect_first") or [])
        check(f"build[{req}]", _any_contains(mods, expect), f"top={mods[:3]}")

    build_check("add distributed tracing", ("http", "websocket", "logging", "middleware", "core.py", "event"))
    build_check("add rate limiting", ("http", "websocket", "auth", "api"))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    summary = {
        "repo": str(HA_REPO),
        "modules": modules,
        "edges": edges,
        "subsystem_count": s.get("subsystem_count"),
        "checks_passed": passed,
        "checks_total": total,
        "all_passed": passed == total,
        "results": [{"name": n, "ok": ok, "detail": d} for n, ok, d in results],
    }
    if verbose:
        print(f"\n{passed}/{total} checks passed — {'ALL PASS' if passed == total else 'FAILURES'}")
    return summary


def main() -> int:
    if not HA_REPO.is_dir():
        print(f"Home Assistant repo not found at {HA_REPO} — set ATLAS_HA_REPO.")
        return 2
    summary = validate(verbose=True)
    return 0 if summary["all_passed"] else 1


# ----------------------------------------------------------------------------
# Optional pytest integration (opt-in to keep the main suite fast)
# ----------------------------------------------------------------------------
def test_home_assistant_real_repo():
    import pytest

    if not HA_REPO.is_dir():
        pytest.skip(f"HA repo not present at {HA_REPO}")
    if os.environ.get("ATLAS_RUN_HA") != "1":
        pytest.skip("set ATLAS_RUN_HA=1 to run the slow Home Assistant validation")
    summary = validate(verbose=False)
    failed = [r["name"] for r in summary["results"] if not r["ok"]]
    assert summary["all_passed"], f"HA validation failures: {failed}"


if __name__ == "__main__":
    raise SystemExit(main())
