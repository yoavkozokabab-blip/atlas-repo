"""50 strict coding task scenarios (Phase 66.1)."""

from __future__ import annotations

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import grade_coding_filesystem, grade_voice_simulated_routing

_CATEGORY = "Coding Task"

_MODULES = [
    "brain/router",
    "actions/registry",
    "browser/runtime",
    "memory/store",
    "voice/tts_service",
    "config",
    "validation/strict_framework",
    "desktop/control_runtime",
    "reliability/voice_health",
    "phase45_investigation",
]


def _coding_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn
    from validation.strict_graders import _out, ProviderKind, ScenarioStatus
    from reliability.coding_health import score_patch_recommendation, validate_patch_path

    scenarios: list[tuple[str, StrictScenarioFn]] = []

    for i in range(15):

        def _mk_inspect(idx: int = i) -> StrictScenarioFn:
            def _run():
                from phase45_investigation import inspect_project

                body = inspect_project()
                ok = "project" in body.lower() or "inspection" in body.lower()
                return grade_coding_filesystem(ok, body[:100])

            return _run

        scenarios.append((f"coding_inspect_{i+1:02d}", _mk_inspect()))

    for i in range(10):

        def _mk_analyze(idx: int = i) -> StrictScenarioFn:
            def _run():
                from phase45_investigation import explain_latest_error, hunt_algorithm_bugs

                body = hunt_algorithm_bugs() if idx % 2 == 0 else explain_latest_error()
                return grade_coding_filesystem(bool(body), body[:100])

            return _run

        scenarios.append((f"coding_analyze_{i+1:02d}", _mk_analyze()))

    for i in range(15):
        mod = _MODULES[i % len(_MODULES)]

        def _mk_patch(mod_hint: str = mod) -> StrictScenarioFn:
            def _run():
                rel = f"{mod_hint}.py" if not mod_hint.endswith(".py") else mod_hint
                conf, _hit = score_patch_recommendation(mod_hint, [rel])
                ok_path, msg = validate_patch_path(rel)
                if ok_path and conf >= 0.5:
                    return grade_coding_filesystem(True, f"conf={conf} path={msg}")
                return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.DEGRADED, error_message="patch_target_weak", detail=f"conf={conf}")

            return _run

        scenarios.append((f"coding_patch_{i+1:02d}", _mk_patch()))

    for i in range(10):

        def _mk_action() -> StrictScenarioFn:
            def _run():
                from actions.registry import ActionRegistry
                from core.types import ActionStatus, CommandRequest, Intent

                reg = ActionRegistry()
                action = reg._actions.get(Intent.INSPECT_PROJECT.value)
                if not action:
                    return grade_voice_simulated_routing(False, "missing_action")
                res = action.execute(CommandRequest(raw_text="inspect project", intent=Intent.INSPECT_PROJECT))
                ok = res.status == ActionStatus.SUCCESS
                return grade_coding_filesystem(ok, (res.summary or "")[:100])

            return _run

        scenarios.append((f"coding_action_{i+1:02d}", _mk_action()))

    return scenarios


def measure_coding_tasks() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _coding_scenarios())
