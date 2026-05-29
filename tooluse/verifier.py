"""Phase 71 — post-action verification.

After every step the executor observes the UI again and asks ``verify_step``
whether the observed state matches the step's success criteria.  Verification
is what makes "no fake success" real: a step is only SUCCESS when the observed
world actually changed as expected.
"""

from __future__ import annotations

from urllib.parse import urlparse

from tooluse.contracts import Observation, PlanStep, StepKind, VerificationResult

# Hosts we treat as "the search engine" (used to confirm OPEN_RESULT navigated away).
_SEARCH_HOSTS = (
    "marginalia.nu", "marginalia-search.com",
    "duckduckgo.com", "google.com", "bing.com", "microsoft.com", "msn.com",
)

_MIN_SUMMARY_TEXT = 50  # chars of visible text required to claim a real summary


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_search_host(url: str) -> bool:
    h = _host(url)
    return any(h == s or h.endswith("." + s) for s in _SEARCH_HOSTS)


def verify_step(
    step: PlanStep,
    before: Observation,
    after: Observation,
) -> VerificationResult:
    """Return whether *after* satisfies *step*'s success criteria."""
    # Any step that needed the world requires a real provider, full stop.
    if step.is_external and not after.real:
        return VerificationResult(False, "no real provider (mock/unavailable not accepted)")

    if step.kind == StepKind.OPEN_SESSION:
        if after.real and after.provider:
            return VerificationResult(True, f"real provider connected: {after.provider}")
        return VerificationResult(False, "browser session not connected")

    if step.kind == StepKind.SEARCH:
        if after.error:
            return VerificationResult(False, f"search error: {after.error[:80]}")
        organic = [l for l in after.links if not _is_search_host(str(l.get("href", "")))]
        if len(organic) < 1:
            return VerificationResult(False, "no organic (off-engine) result links found")
        return VerificationResult(True, f"{len(organic)} organic result link(s) on results page")

    if step.kind == StepKind.OPEN_RESULT:
        if _is_search_host(after.url) or not after.url:
            return VerificationResult(False, f"did not navigate off search engine (url={after.url or 'n/a'})")
        if not (after.title or "").strip():
            return VerificationResult(False, "opened page has empty title")
        return VerificationResult(True, f"navigated to {_host(after.url)} title={after.title[:50]!r}")

    if step.kind in (StepKind.OBSERVE, StepKind.SUMMARIZE):
        if len((after.visible_text or "").strip()) < _MIN_SUMMARY_TEXT:
            return VerificationResult(False, "page has no substantial visible text to summarize")
        return VerificationResult(True, f"{len(after.visible_text)} chars of visible text available")

    return VerificationResult(False, f"no verifier for step kind {step.kind.value}")


def build_summary(obs: Observation, *, max_chars: int = 600) -> str:
    """Deterministic, honest summary from a real observation (no LLM, no invention)."""
    parts: list[str] = []
    if obs.title:
        parts.append(f"Title: {obs.title}")
    if obs.url:
        parts.append(f"URL: {obs.url}")
    if obs.headings:
        parts.append("Headings: " + " | ".join(obs.headings[:5]))
    text = (obs.visible_text or "").strip().replace("\n", " ")
    if text:
        parts.append("Excerpt: " + text[:max_chars])
    return "\n".join(parts) if parts else "No content observed."
