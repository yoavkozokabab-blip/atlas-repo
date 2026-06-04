"""Phase 140 — scan reliability: degraded-scan detection, failure taxonomy, retry.

Reliability hardening only — no new intelligence, concepts, billing or UI. This
module classifies the *outcome* of a scan so Syron can:

  * detect a degraded scan immediately (0 modules, 0 edges, partial/timed-out
    graph, unresolved-import explosion) and surface a warning,
  * decide whether a failure is a SAFE TRANSIENT one worth retrying once,
  * give every failure a stable taxonomy category for the reliability dashboard.

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

# Categories that represent a real reliability fault (vs. a healthy or
# legitimately-empty result).
FAULT_CATEGORIES = frozenset({
    SCAN_CRASH, SCAN_FAILED, ZERO_MODULE_SCAN, ZERO_EDGE_GRAPH, PARTIAL_GRAPH,
    TIMEOUT, UNRESOLVED_EXPLOSION, MEMORY_PRESSURE,
})

# Only these are safe to retry automatically — transient, side-effect-free.
RETRYABLE_CATEGORIES = frozenset({ZERO_MODULE_SCAN})

# Thresholds (conservative; tunable).
_MANY_FILES = 500            # below this, 0 modules may just be an empty repo
_MIN_MODULES_FOR_EDGES = 8   # below this, 0 edges is unremarkable
_UNRESOLVED_RATIO = 0.85     # fraction of imports unresolved to flag explosion
_UNRESOLVED_MIN = 50         # absolute unresolved imports to flag explosion
_MEMORY_BUDGET_MB = 2048     # peak RSS budget for a single scan


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
    timed_out = bool(build.get("timed_out") or scan.get("jarvis_timed_out")
                     or scan.get("timed_out"))
    partial = bool(build.get("partial") or scan.get("jarvis_partial"))

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
