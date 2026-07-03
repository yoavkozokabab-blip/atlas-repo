"""Phase 140 / 158 — scan reliability: degraded-scan detection, failure taxonomy, retry.

Reliability hardening only — no new intelligence, concepts, billing or UI. This
module classifies the *outcome* of a scan so Atlas can:

  * detect a degraded scan immediately (0 modules, 0 edges, partial/timed-out
    graph, unresolved-import explosion) and surface a warning,
  * decide whether a failure is a SAFE TRANSIENT one worth retrying once,
  * give every failure a stable taxonomy category for the reliability dashboard.

Phase 158: added unsupported_language_limited — files > threshold but modules < threshold
means the language is not well-supported; this is NOT reported as "healthy".

Pure functions over the scan-result dict; safe to call anywhere.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Failure taxonomy (stable categories used by the reliability dashboard)
# --------------------------------------------------------------------------
OK = "ok"
SCAN_CRASH = "scan_crash"               # exception during scan
SCAN_FAILED = "scan_failed"             # scan returned ok=False
ZERO_MODULE_SCAN = "zero_module_scan"   # many files, 0 modules indexed
ZERO_EDGE_GRAPH = "zero_edge_graph"     # modules built, 0 dependency edges
PARTIAL_GRAPH = "partial_graph"         # degraded / partial graph
TIMEOUT = "timeout_failure"             # graph build hit its deadline
UNRESOLVED_EXPLOSION = "unresolved_import_explosion"  # most imports unresolved
MEMORY_PRESSURE = "memory_pressure"     # peak RSS over budget (harness-measured)
EMPTY_REPO = "empty_repo"               # genuinely tiny/empty repo (not a fault)
UNSUPPORTED_LANGUAGE = "unsupported_language_limited"  # P158: many files, few modules

# Categories that represent a real reliability fault (vs. a healthy or
# legitimately-empty result).
FAULT_CATEGORIES = frozenset({
    SCAN_CRASH, SCAN_FAILED, ZERO_MODULE_SCAN, ZERO_EDGE_GRAPH, PARTIAL_GRAPH,
    TIMEOUT, UNRESOLVED_EXPLOSION, MEMORY_PRESSURE, UNSUPPORTED_LANGUAGE,
})

# Only these are safe to retry automatically — transient, side-effect-free.
RETRYABLE_CATEGORIES = frozenset({ZERO_MODULE_SCAN})

# Thresholds (conservative; tunable).
_MANY_FILES = 500            # below this, 0 modules may just be an empty repo
_MIN_MODULES_FOR_EDGES = 8   # below this, 0 edges is unremarkable
_UNRESOLVED_RATIO = 0.85     # fraction of imports unresolved to flag explosion
_UNRESOLVED_MIN = 50         # absolute unresolved imports to flag explosion
_MEMORY_BUDGET_MB = 2048     # peak RSS budget for a single scan

# P158 FIX 4 — unsupported language threshold.
# If a repo has many files but Atlas built almost no modules, the language is
# outside Atlas's strong coverage (Go, Java, C#, Rust, etc.).
# These thresholds are intentionally conservative to avoid false positives on
# repos that genuinely have few modules (e.g. micro-services).
_LANG_LIMIT_FILES = 1000     # must have more than this many files ...
_LANG_LIMIT_MODULES = 25     # ... but fewer than this modules → unsupported_language_limited

# Human-readable health labels for the UI (maps category → short label).
_HEALTH_LABELS: Dict[str, str] = {
    OK: "healthy",
    EMPTY_REPO: "empty",
    PARTIAL_GRAPH: "partial",
    ZERO_EDGE_GRAPH: "degraded",
    ZERO_MODULE_SCAN: "degraded",
    TIMEOUT: "degraded",
    UNRESOLVED_EXPLOSION: "partial",
    UNSUPPORTED_LANGUAGE: "unsupported_language_limited",
    MEMORY_PRESSURE: "degraded",
    SCAN_CRASH: "failed",
    SCAN_FAILED: "failed",
}


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _float(v: Any) -> float:
    try:
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


def classify_scan(scan: Dict[str, Any], *, peak_rss_mb: Optional[float] = None) -> Dict[str, Any]:
    """Classify a scan-result dict into a reliability assessment.

    Returns ``{healthy, degraded, category, severity, signals, warnings,
    retryable}``. ``category`` is the single most important taxonomy label;
    ``signals`` lists every issue detected.
    """
    signals: List[str] = []
    warnings: List[str] = []

    if not isinstance(scan, dict):
        return _result(SCAN_CRASH, ["scan result was not a dict"],
                       ["Scan produced no result object."])

    # Hard failures first.
    if scan.get("error") and not scan.get("ok", True):
        return _result(SCAN_FAILED, [f"scan ok=False: {scan.get('code') or scan.get('error')}"],
                       [f"Scan failed: {scan.get('error')}"])

    files = _int(scan.get("file_count")) or _int(scan.get("files_discovered"))
    modules = _int(scan.get("module_count"))
    edges = _int(scan.get("dependency_edges"))
    detail = str(scan.get("graph_detail") or "")
    degraded = bool(scan.get("degraded"))
    unresolved = _int(scan.get("unresolved_imports"))
    unresolved_ratio = _float(scan.get("unresolved_ratio"))
    duration = _float(scan.get("scan_duration_seconds"))
    build = scan.get("graph_build") or {}
    timed_out = bool(build.get("timed_out") or scan.get("atlas_timed_out")
                     or scan.get("timed_out"))
    partial = bool(build.get("partial") or scan.get("atlas_partial"))

    # Memory pressure (harness-measured; optional).
    if peak_rss_mb is not None and peak_rss_mb > _MEMORY_BUDGET_MB:
        signals.append(f"peak RSS {peak_rss_mb:.0f} MB > {_MEMORY_BUDGET_MB} MB budget")
        warnings.append(f"High memory use during scan ({peak_rss_mb:.0f} MB).")

    # Timeout is a timeout regardless of how many modules were built before it.
    if timed_out:
        signals.append("graph build timed out")
        warnings.append("Scan timed out before the full graph was built; results are partial.")
        return _result(TIMEOUT, signals, warnings, severity="high")

    # Degenerate graph: files present but nothing indexed.
    if modules == 0:
        if files >= _MANY_FILES:
            signals.append(f"0 modules from {files} files")
            warnings.append(f"Degraded scan: 0 modules indexed from {files} files — retrying.")
            return _result(ZERO_MODULE_SCAN, signals, warnings, severity="high")
        signals.append(f"0 modules from {files} files (small/empty repo)")
        return _result(EMPTY_REPO, signals,
                       [f"Repository has no indexable modules ({files} files)."] if files else [],
                       degraded=False)

    # P158 FIX 4 — large repo with almost no modules means unsupported language.
    # Must be checked AFTER zero-module (0 modules is a different fault class).
    if files > _LANG_LIMIT_FILES and modules < _LANG_LIMIT_MODULES:
        signals.append(
            f"{files} files scanned but only {modules} graph modules built "
            f"(ratio {modules/files:.4f})"
        )
        warnings.append(
            f"Atlas scanned {files:,} files but only built {modules} graph modules. "
            "This repository is currently outside Atlas's strong graph coverage — "
            "the primary language may not be well-supported (Go, Java, C#, Rust, etc.). "
            "Build Plan, Investigation, and Impact results will be weak. "
            "See: Atlas currently has strong support for Python and TypeScript."
        )
        return _result(UNSUPPORTED_LANGUAGE, signals, warnings, severity="high")

    # Partial / degraded graph.
    if partial or (degraded and detail != "imports"):
        signals.append(f"partial/degraded graph (detail={detail or 'unknown'})")
        warnings.append("Graph is partial/degraded; impact and architecture may be incomplete.")
        return _result(PARTIAL_GRAPH, signals, warnings, severity="medium")

    # Zero edges despite real module count.
    if edges == 0 and modules >= _MIN_MODULES_FOR_EDGES:
        signals.append(f"0 dependency edges across {modules} modules")
        warnings.append(f"No dependency edges resolved across {modules} modules — "
                        "impact analysis will be weak.")
        return _result(ZERO_EDGE_GRAPH, signals, warnings, severity="medium")

    # Unresolved-import explosion.
    if unresolved >= _UNRESOLVED_MIN and unresolved_ratio >= _UNRESOLVED_RATIO:
        signals.append(f"{unresolved} unresolved imports ({unresolved_ratio:.0%} of imports)")
        warnings.append(f"{unresolved_ratio:.0%} of imports are unresolved — "
                        "cross-file impact may be under-counted.")
        return _result(UNRESOLVED_EXPLOSION, signals, warnings, severity="medium")

    # Otherwise-clean graph but over the memory budget is its own fault category.
    if peak_rss_mb is not None and peak_rss_mb > _MEMORY_BUDGET_MB:
        return _result(MEMORY_PRESSURE, signals, warnings, severity="medium")
    # Healthy (note slow scans informationally, not as a fault).
    if duration >= 300:
        signals.append(f"slow scan ({duration:.0f}s)")
    return _result(OK, signals or ["graph built cleanly"], warnings, degraded=False, severity="none")


def _result(category: str, signals: List[str], warnings: List[str], *,
            degraded: Optional[bool] = None, severity: str = "high") -> Dict[str, Any]:
    fault = category in FAULT_CATEGORIES
    if degraded is None:
        degraded = fault
    return {
        "healthy": not fault,
        "degraded": bool(degraded),
        "category": category,
        "severity": "none" if not fault else severity,
        "signals": signals,
        "warnings": warnings,
        "retryable": category in RETRYABLE_CATEGORIES,
    }


def is_retryable(assessment: Dict[str, Any]) -> bool:
    """A failure is retryable only if it is a safe, transient category."""
    return bool(assessment.get("retryable")) and assessment.get("category") in RETRYABLE_CATEGORIES


def scan_warnings(scan: Dict[str, Any], *, peak_rss_mb: Optional[float] = None) -> List[str]:
    """Immediate human-readable warnings for a scan (empty if healthy)."""
    return classify_scan(scan, peak_rss_mb=peak_rss_mb).get("warnings", [])


def graph_health_label(scan: Dict[str, Any], *, peak_rss_mb: Optional[float] = None) -> str:
    """Return a short human-readable health label for a scan result.

    Returned values: healthy | partial | degraded | unsupported_language_limited |
    empty | failed.  Never returns a category that over-represents the quality.
    """
    assessment = classify_scan(scan, peak_rss_mb=peak_rss_mb)
    cat = assessment.get("category") or OK
    return _HEALTH_LABELS.get(cat, cat)


def confidence_cap_for_scan(scan: Dict[str, Any]) -> str:
    """P158 FIX 6 — Return the maximum confidence Atlas may claim given scan quality.

    This cap should be applied to every plan/investigation/impact result so that
    a degraded or unsupported-language scan can never produce a 'high' confidence
    claim.

    Returns: 'high' | 'medium' | 'low'
    """
    label = graph_health_label(scan)
    if label == "healthy":
        return "high"
    if label == "partial":
        # partial graph: some structure but incomplete — cap at medium
        return "medium"
    if label == "degraded":
        # degraded (zero edges, timeout, zero modules): some data but unreliable — cap at medium
        return "medium"
    # unsupported_language_limited, failed, empty → low
    return "low"


# Order used to compare confidence levels. Compound labels ("medium-high",
# "low-medium") are reduced to their strongest component for comparison.
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def _confidence_rank(label: str) -> int:
    """Rank a confidence label (0=low,1=medium,2=high). Compound labels use the
    strongest component, e.g. 'medium-high' → high, 'low-medium' → medium."""
    if not label:
        return 0
    parts = str(label).split("-")
    return max(_CONFIDENCE_ORDER.get(p, 0) for p in parts)


def _rank_to_label(rank: int) -> str:
    for name, value in _CONFIDENCE_ORDER.items():
        if value == rank:
            return name
    return "low"


def calibrate_confidence_cap(
    scan: Dict[str, Any],
    *,
    evidence_count: int = 0,
    resolution: str = "resolved",
) -> str:
    """Phase 161 — strict confidence ceiling.

    A result may never claim more confidence than ALL of these allow:
      * graph/scan health (``confidence_cap_for_scan``),
      * evidence count — 0 signals → low, 1 → at most medium, ≥2 → high allowed,
      * target/intent resolution — 'unresolved' → low, 'partial' → at most medium.

    High confidence therefore requires a healthy graph, ≥2 grounded evidence
    signals, and a fully resolved target. Returns 'low' | 'medium' | 'high'.
    """
    caps = [_confidence_rank(confidence_cap_for_scan(scan))]

    if evidence_count <= 0:
        caps.append(_CONFIDENCE_ORDER["low"])
    elif evidence_count == 1:
        caps.append(_CONFIDENCE_ORDER["medium"])
    else:
        caps.append(_CONFIDENCE_ORDER["high"])

    res = (resolution or "resolved").lower()
    if res in ("unresolved", "none", "not_resolved"):
        caps.append(_CONFIDENCE_ORDER["low"])
    elif res in ("partial", "heuristic", "outside_graph"):
        caps.append(_CONFIDENCE_ORDER["medium"])
    else:
        caps.append(_CONFIDENCE_ORDER["high"])

    return _rank_to_label(min(caps))
