"""Phase 78 — verification of tool results.

Verification is what makes "no fake success" structural: a tool result is only
marked ``verified`` when its declared post-condition contract holds against the
actual result. A failed/blocked underlying result can never be verified.
"""

from __future__ import annotations

from tools.spec import ToolResult, ToolSpec, ToolStatus, Verification

# Labels that indicate a non-real / simulated provider — never accepted as real.
_UNTRUSTED_PROVIDER_LABELS = {"mock", "unavailable", "degraded", "simulated"}


def _looks_mock(result: ToolResult) -> bool:
    blob = f"{result.summary} {result.data}".lower()
    if "mock mode" in blob or "no real external access" in blob:
        return True
    fs = str(result.data.get("final_status", "")).lower()
    if fs in {"blocked_unavailable"}:
        return True
    prov = str(result.data.get("provider", "")).lower()
    return prov in _UNTRUSTED_PROVIDER_LABELS


def verify(spec: ToolSpec, result: ToolResult) -> tuple[bool, str]:
    """Apply the tool's declared verification contract. Returns (ok, reason)."""
    # Nothing verifies on a non-success underlying result.
    if result.status != ToolStatus.SUCCESS:
        return False, f"status={result.status.value}"

    reasons: list[str] = []
    for check in spec.verification:
        ok, why = _check_one(check, spec, result)
        if not ok:
            return False, why
        reasons.append(why)
    return True, "; ".join(reasons) or "ok"


def _check_one(check: Verification, spec: ToolSpec, result: ToolResult) -> tuple[bool, str]:
    if check == Verification.RESULT_SUCCESS:
        return True, "result_success"

    if check == Verification.NON_EMPTY_SUMMARY:
        if len((result.summary or "").strip()) > 0:
            return True, "non_empty_summary"
        return False, "empty summary"

    if check == Verification.PROVIDER_REAL:
        if _looks_mock(result):
            return False, "untrusted/mock/unavailable provider"
        return True, "provider_real"

    if check == Verification.SCHEMA_VALID:
        required = list((spec.output_schema or {}).get("required", []))
        missing = [k for k in required if k not in (result.data or {})]
        if missing:
            return False, f"missing output keys: {missing}"
        return True, "schema_valid"

    if check == Verification.CROSS_SOURCE:
        sources = result.data.get("sources") or result.data.get("urls_opened") or []
        if isinstance(sources, list) and len(sources) >= 2:
            return True, "cross_source>=2"
        return False, "fewer than 2 sources"

    return False, f"unknown verification {check}"
