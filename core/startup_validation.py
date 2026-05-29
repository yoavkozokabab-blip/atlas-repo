"""Startup validation (Sprint 2 / S2.4 + S2.5).

Two checks run once at startup, before any command is accepted:

S2.4 — Intent coverage
    Every intent in IMPLEMENTED_INTENTS must have a registered handler in
    ActionRegistry.  A missing handler means the user can issue the command,
    pass security validation, and then get a silent "not implemented" response
    with no explanation.  We surface this loudly at startup instead.

S2.5 — Config sanity
    Critical runtime invariants that cannot be deduced from config.py alone:
    - DATA_DIR exists and is writable
    - IMPLEMENTED_INTENTS ⊆ ALLOWED_INTENTS (every implemented intent is allowed)
    - IMPLEMENTED_INTENTS and ALLOWED_INTENTS are non-empty
    These errors are logged individually so the developer sees all problems at
    once rather than fixing one and discovering another.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.logger import setup_logger

if TYPE_CHECKING:
    from actions.registry import ActionRegistry
    from core.runtime_state import RuntimeState

logger = setup_logger("jarvis.core.startup_validation")


class ValidationSeverity(str, Enum):
    """Startup check severity (Sprint 3.2 / B04)."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class StartupValidationIssue:
    """One startup validation finding with severity."""

    message: str
    severity: ValidationSeverity
    check: str = ""

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# S2.4 — Intent coverage
# ---------------------------------------------------------------------------

def validate_intent_coverage(registry: "ActionRegistry") -> list[str]:
    """
    Verify that every intent in IMPLEMENTED_INTENTS has a registered handler.

    Returns list of missing intent values (empty = all handlers present).
    Logs CRITICAL for each missing handler.
    """
    from config import IMPLEMENTED_INTENTS

    # Intents handled inline by ActionRegistry.execute() or CommandRouter —
    # they are intentionally not registered as standalone handler objects.
    _INLINE_HANDLED: frozenset[str] = frozenset({"shutdown_jarvis"})

    missing: list[str] = []
    for intent_value in sorted(IMPLEMENTED_INTENTS):
        if intent_value in _INLINE_HANDLED:
            continue
        if not registry.has(intent_value):
            missing.append(intent_value)
            logger.critical(
                "STARTUP: no handler registered for implemented intent '%s'",
                intent_value,
            )
    if missing:
        logger.critical(
            "STARTUP: %d implemented intent(s) have no handler — "
            "commands will return 'not_implemented' at runtime: %s",
            len(missing),
            missing[:10],
        )
    else:
        logger.info("STARTUP: intent coverage OK (%d intents registered)", len(IMPLEMENTED_INTENTS))
    return missing


# ---------------------------------------------------------------------------
# S2.5 — Config sanity
# ---------------------------------------------------------------------------

def validate_config() -> list[StartupValidationIssue]:
    """
    Check critical runtime invariants.

    Returns issues with severity (empty = all checks pass).
    """
    import config as cfg

    issues: list[StartupValidationIssue] = []

    # --- DATA_DIR must be writable ---
    data_dir = Path(cfg.DATA_DIR)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".startup_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        msg = f"DATA_DIR '{data_dir}' is not writable: {exc}"
        issues.append(
            StartupValidationIssue(msg, ValidationSeverity.CRITICAL, check="data_dir")
        )
        logger.critical("STARTUP config: %s", msg)

    # --- IMPLEMENTED_INTENTS must be a non-empty frozenset ---
    impl = getattr(cfg, "IMPLEMENTED_INTENTS", None)
    if not isinstance(impl, frozenset) or len(impl) == 0:
        msg = "IMPLEMENTED_INTENTS is missing or empty — no intents will be routed"
        issues.append(
            StartupValidationIssue(msg, ValidationSeverity.CRITICAL, check="implemented_intents")
        )
        logger.critical("STARTUP config: %s", msg)

    # --- ALLOWED_INTENTS must be a non-empty frozenset ---
    allowed = getattr(cfg, "ALLOWED_INTENTS", None)
    if not isinstance(allowed, frozenset) or len(allowed) == 0:
        msg = "ALLOWED_INTENTS is missing or empty — all commands will be blocked"
        issues.append(
            StartupValidationIssue(msg, ValidationSeverity.CRITICAL, check="allowed_intents")
        )
        logger.critical("STARTUP config: %s", msg)

    # --- IMPLEMENTED ⊆ ALLOWED ---
    if isinstance(impl, frozenset) and isinstance(allowed, frozenset):
        not_allowed = impl - allowed
        if not_allowed:
            msg = (
                f"{len(not_allowed)} implemented intent(s) are not in ALLOWED_INTENTS "
                f"(they will be blocked at runtime): {sorted(not_allowed)[:5]}"
            )
            issues.append(
                StartupValidationIssue(msg, ValidationSeverity.CRITICAL, check="intent_subset")
            )
            logger.critical("STARTUP config: %s", msg)

    if not issues:
        logger.info(
            "STARTUP: config OK (implemented=%d allowed=%d data_dir=%s)",
            len(impl) if isinstance(impl, frozenset) else 0,
            len(allowed) if isinstance(allowed, frozenset) else 0,
            data_dir,
        )
    return issues


def validate_config_messages() -> list[str]:
    """Backward-compatible: config issues as plain message strings."""
    return [issue.message for issue in validate_config()]


# ---------------------------------------------------------------------------
# S3.6 — Win32 / dependency availability checks
# ---------------------------------------------------------------------------

def dependency_issues_from_availability(available: dict[str, bool]) -> list[StartupValidationIssue]:
    """Map missing optional deps to degraded-mode warnings (never fatal)."""
    issues: list[StartupValidationIssue] = []
    labels = {
        "win32gui": "win32gui (desktop window control)",
        "tesseract": "tesseract OCR",
        "playwright": "playwright (real browser)",
    }
    for dep, ok in available.items():
        if ok:
            continue
        label = labels.get(dep, dep)
        issues.append(
            StartupValidationIssue(
                f"Optional dependency missing: {label}",
                ValidationSeverity.WARNING,
                check=f"dependency:{dep}",
            )
        )
    return issues


def validate_win32_dependencies() -> dict[str, bool]:
    """
    Check availability of optional Windows / browser dependencies.

    Returns {dep_name: available} for reporting in startup health display.
    Never raises; missing deps are False not errors.
    """
    import importlib
    import shutil

    results: dict[str, bool] = {}

    # win32gui — needed for window control and screen-capture
    try:
        importlib.import_module("win32gui")
        results["win32gui"] = True
    except ImportError:
        results["win32gui"] = False
        logger.warning("STARTUP: win32gui not importable — desktop window control unavailable")

    # Tesseract OCR — needed for read_screen / OCR pipeline
    results["tesseract"] = shutil.which("tesseract") is not None
    if not results["tesseract"]:
        logger.warning("STARTUP: tesseract not found in PATH — OCR features unavailable")

    # Playwright — needed for real browser automation (S6.4)
    try:
        importlib.import_module("playwright.sync_api")
        results["playwright"] = True
    except ImportError:
        results["playwright"] = False
        logger.info("STARTUP: playwright not importable — browser will use mock provider")

    logger.info(
        "STARTUP: dependency check: %s",
        {k: ("available" if v else "missing") for k, v in results.items()},
    )
    return results


# ---------------------------------------------------------------------------
# Combined entry point (called from runtime_bootstrap)
# ---------------------------------------------------------------------------

def run_startup_validation(
    registry: "ActionRegistry | None" = None,
    *,
    abort_on_critical: bool = False,
) -> dict[str, Any]:
    """
    Run all startup validations.

    Returns dict with:
    - ``config``: list[StartupValidationIssue]
    - ``intent_coverage``: list[str] (missing handler intent values)
    - ``dependencies_missing``: list[str]
    - ``issues``: combined StartupValidationIssue list

    Missing optional dependencies and intent coverage gaps mark *degraded*
    mode; they never abort.  Critical config errors mark degraded unless
    *abort_on_critical* requests ``sys.exit(1)`` (legacy tests only).
    """
    results: dict[str, Any] = {}
    all_issues: list[StartupValidationIssue] = []

    config_issues = validate_config()
    results["config"] = config_issues
    all_issues.extend(config_issues)

    if registry is not None:
        coverage_errors = validate_intent_coverage(registry)
        results["intent_coverage"] = coverage_errors
        for intent_value in coverage_errors:
            all_issues.append(
                StartupValidationIssue(
                    f"No handler for implemented intent '{intent_value}'",
                    ValidationSeverity.WARNING,
                    check="intent_coverage",
                )
            )
    else:
        results["intent_coverage"] = []

    dep_available = validate_win32_dependencies()
    dep_missing = [dep for dep, ok in dep_available.items() if not ok]
    results["dependencies_missing"] = dep_missing
    all_issues.extend(dependency_issues_from_availability(dep_available))

    results["issues"] = all_issues

    if abort_on_critical and any(
        i.severity == ValidationSeverity.CRITICAL for i in config_issues
    ):
        logger.critical("STARTUP: aborting due to critical config errors")
        print(
            "\n[JARVIS STARTUP ERROR] Critical configuration problems detected:\n"
            + "\n".join(f"  - {i.message}" for i in config_issues),
            flush=True,
        )
        sys.exit(1)

    return results


def apply_startup_validation_to_runtime(
    runtime: "RuntimeState",
    validation: dict[str, Any],
    *,
    print_summary: bool = True,
) -> None:
    """Mark runtime degraded for critical config or missing optional deps (B04/B07)."""
    issues: list[StartupValidationIssue] = list(validation.get("issues") or [])
    critical = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
    warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

    if critical or warnings:
        runtime.mark_degraded(
            "; ".join(i.message for i in (critical + warnings)[:5])
        )
        for issue in critical + warnings:
            runtime.record_event(
                "startup_validation",
                severity=issue.severity.value,
                check=issue.check,
                message=issue.message[:200],
            )
        if print_summary:
            if critical:
                print(
                    "[JARVIS] Runtime DEGRADED — critical startup checks failed:",
                    flush=True,
                )
                for issue in critical:
                    print(f"  - {issue.message}", flush=True)
            if warnings:
                print(
                    "[JARVIS] Runtime DEGRADED — optional dependencies missing:",
                    flush=True,
                )
                for issue in warnings:
                    print(f"  - {issue.message}", flush=True)
    else:
        runtime.clear_degraded()
