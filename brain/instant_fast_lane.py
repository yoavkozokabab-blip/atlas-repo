"""Instant voice fast-lane classification only.

This module never executes commands. It only returns high-confidence
CommandRequest objects that still go through router/security/registry.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.types import CommandRequest, Intent


@dataclass(frozen=True)
class _FastLanePhrase:
    phrase: str
    intent: Intent
    confidence: float = 0.94
    params: dict | None = None


_FAST_LANE_PHRASES: tuple[_FastLanePhrase, ...] = (
    _FastLanePhrase("open dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.97),
    _FastLanePhrase("open the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.97),
    _FastLanePhrase("can you open the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _FastLanePhrase("bring up the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _FastLanePhrase("show jarvis status", Intent.SHOW_JARVIS_STATUS, 0.96),
    _FastLanePhrase("what am i doing", Intent.WHAT_AM_I_DOING, 0.96),
    _FastLanePhrase("what was i working on", Intent.WHAT_WERE_WE_DOING, 0.95),
    _FastLanePhrase("what were we doing", Intent.WHAT_WERE_WE_DOING, 0.95),
    _FastLanePhrase("continue from yesterday", Intent.WHAT_WERE_WE_DOING, 0.92),
    _FastLanePhrase("open the thing we were working on", Intent.WHAT_WERE_WE_DOING, 0.90),
    _FastLanePhrase("describe screen", Intent.DESCRIBE_SCREEN, 0.96),
    _FastLanePhrase("describe the screen", Intent.DESCRIBE_SCREEN, 0.96),
    _FastLanePhrase("whats on my screen", Intent.DESCRIBE_SCREEN, 0.96),
    _FastLanePhrase("what is on my screen", Intent.DESCRIBE_SCREEN, 0.96),
    _FastLanePhrase("analyze active window", Intent.ANALYZE_ACTIVE_WINDOW, 0.96),
    _FastLanePhrase("analyze the active window", Intent.ANALYZE_ACTIVE_WINDOW, 0.96),
    _FastLanePhrase("look at this window", Intent.ANALYZE_ACTIVE_WINDOW, 0.95),
    _FastLanePhrase("show voice debug", Intent.SHOW_VOICE_DEBUG, 0.96),
    _FastLanePhrase("test direct speech", Intent.TEST_DIRECT_SPEECH, 0.96),
    _FastLanePhrase("verify direct speech backend", Intent.VERIFY_DIRECT_SPEECH_BACKEND, 0.96),
    _FastLanePhrase(
        "force verified direct speech confirm",
        Intent.FORCE_VERIFIED_DIRECT_SPEECH,
        0.96,
    ),
    _FastLanePhrase("show audio status", Intent.SHOW_AUDIO_STATUS, 0.96),
    _FastLanePhrase("tool mode status", Intent.TOOL_MODE_STATUS, 0.96),
    _FastLanePhrase("phase 45 status", Intent.PHASE45_STATUS, 0.97),
    _FastLanePhrase("phase 46 status", Intent.PHASE46_STATUS, 0.97),
    _FastLanePhrase("inspect project", Intent.INSPECT_PROJECT, 0.97),
    _FastLanePhrase("find failing tests", Intent.FIND_FAILING_TESTS, 0.97),
    _FastLanePhrase("explain latest error", Intent.EXPLAIN_LATEST_ERROR, 0.97),
    _FastLanePhrase("compare live vs backtest", Intent.COMPARE_LIVE_VS_BACKTEST, 0.97),
    _FastLanePhrase("trace algorithm behavior", Intent.TRACE_ALGORITHM_BEHAVIOR, 0.97),
    _FastLanePhrase("diff live and backtest logic", Intent.DIFF_LIVE_BACKTEST_LOGIC, 0.97),
    _FastLanePhrase("hunt algorithm bugs", Intent.HUNT_ALGORITHM_BUGS, 0.97),
    _FastLanePhrase("replay latest signal", Intent.REPLAY_LATEST_SIGNAL, 0.97),
    _FastLanePhrase("verify top hypothesis", Intent.VERIFY_TOP_HYPOTHESIS, 0.97),
    _FastLanePhrase("show replay timeline", Intent.SHOW_REPLAY_TIMELINE, 0.97),
    _FastLanePhrase("investigation confidence report", Intent.INVESTIGATION_CONFIDENCE_REPORT, 0.97),
    _FastLanePhrase("simulate patch for top hypothesis", Intent.SIMULATE_PATCH_TOP_HYPOTHESIS, 0.97),
    _FastLanePhrase("run patch simulation", Intent.RUN_PATCH_SIMULATION, 0.97),
    _FastLanePhrase("compare replay before after", Intent.COMPARE_REPLAY_BEFORE_AFTER, 0.97),
    _FastLanePhrase("estimate patch impact", Intent.ESTIMATE_PATCH_IMPACT, 0.97),
    _FastLanePhrase("generate patch simulation report", Intent.GENERATE_PATCH_SIMULATION_REPORT, 0.97),
    _FastLanePhrase("run historical validation sweep", Intent.RUN_HISTORICAL_VALIDATION_SWEEP, 0.97),
    _FastLanePhrase("show validation sweep", Intent.SHOW_VALIDATION_SWEEP, 0.97),
    _FastLanePhrase("estimate production risk", Intent.ESTIMATE_PRODUCTION_RISK, 0.97),
    _FastLanePhrase("recommend production action", Intent.RECOMMEND_PRODUCTION_ACTION, 0.97),
    _FastLanePhrase("audit price integrity", Intent.AUDIT_PRICE_INTEGRITY, 0.97),
    _FastLanePhrase("find close price mismatches", Intent.FIND_CLOSE_PRICE_MISMATCHES, 0.97),
    _FastLanePhrase("check timestamp alignment", Intent.CHECK_TIMESTAMP_ALIGNMENT, 0.97),
    _FastLanePhrase("audit execution path", Intent.AUDIT_EXECUTION_PATH, 0.97),
    _FastLanePhrase("explain zero execution attempts", Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS, 0.97),
    _FastLanePhrase("show execution blockers", Intent.SHOW_EXECUTION_BLOCKERS, 0.97),
    _FastLanePhrase("inspect execution adapter", Intent.INSPECT_EXECUTION_ADAPTER, 0.97),
    _FastLanePhrase("compare signal count to order attempts", Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS, 0.97),
    _FastLanePhrase("generate execution investigation report", Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT, 0.97),
    _FastLanePhrase("reconstruct execution flow", Intent.RECONSTRUCT_EXECUTION_FLOW, 0.97),
    _FastLanePhrase("explain top execution blocker", Intent.EXPLAIN_TOP_EXECUTION_BLOCKER, 0.97),
    _FastLanePhrase("rank dead signal causes", Intent.RANK_DEAD_SIGNAL_CAUSES, 0.97),
    _FastLanePhrase("generate execution flow report", Intent.GENERATE_EXECUTION_FLOW_REPORT, 0.97),
    _FastLanePhrase("simulate execution cleanup patch", Intent.SIMULATE_EXECUTION_CLEANUP_PATCH, 0.97),
    _FastLanePhrase("show stale open positions", Intent.SHOW_STALE_OPEN_POSITIONS, 0.97),
    _FastLanePhrase("propose execution cleanup patch", Intent.PROPOSE_EXECUTION_CLEANUP_PATCH, 0.97),
    _FastLanePhrase("generate execution cleanup report", Intent.GENERATE_EXECUTION_CLEANUP_REPORT, 0.97),
    _FastLanePhrase("validate patch safety", Intent.VALIDATE_PATCH_SAFETY, 0.97),
    _FastLanePhrase("validate patch safe", Intent.VALIDATE_PATCH_SAFETY, 0.97),
    _FastLanePhrase("show approved patch", Intent.SHOW_APPROVED_PATCH, 0.97),
    _FastLanePhrase("replay after patch", Intent.REPLAY_AFTER_PATCH, 0.97),
    _FastLanePhrase("replay validation", Intent.REPLAY_AFTER_PATCH, 0.97),
    _FastLanePhrase("run patch workflow", Intent.RUN_PATCH_WORKFLOW, 0.97),
    _FastLanePhrase("run patch workflow confirm", Intent.RUN_PATCH_WORKFLOW, 0.97),
    _FastLanePhrase("show patch workflow status", Intent.SHOW_PATCH_WORKFLOW_STATUS, 0.97),
    _FastLanePhrase("review latest patch", Intent.REVIEW_LATEST_PATCH, 0.95),
    _FastLanePhrase("show failing tests", Intent.SHOW_FAILING_TESTS, 0.95),
    _FastLanePhrase("explain this error", Intent.EXPLAIN_THIS_ERROR, 0.95),
    _FastLanePhrase("check why this failed", Intent.EXPLAIN_THIS_ERROR, 0.94),
    _FastLanePhrase("tell me what went wrong", Intent.EXPLAIN_THIS_ERROR, 0.94),
    _FastLanePhrase("make a plan", Intent.ASSISTANT_PLAN, 0.94),
    _FastLanePhrase("show voice latency budget", Intent.SHOW_LATENCY_STATUS, 0.97, {"budget": "voice"}),
)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = value.replace("'", "").replace("`", "").replace("\u2019", "")
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _matches(normalized: str, phrase: str) -> bool:
    if normalized == phrase:
        return True
    return normalized.startswith(phrase + " ") or normalized.endswith(" " + phrase)


def match_instant_fast_lane(text: str) -> CommandRequest | None:
    """Return a fast-lane classification when instant mode is enabled."""
    try:
        import config as cfg

        if getattr(cfg, "VOICE_RUNTIME_STABLE", False):
            return None
        if not getattr(cfg, "VOICE_LATENCY_INSTANT", False):
            return None
    except Exception:
        return None

    normalized = _normalize(text)
    if not normalized:
        return None

    best: _FastLanePhrase | None = None
    for item in _FAST_LANE_PHRASES:
        phrase = _normalize(item.phrase)
        if _matches(normalized, phrase):
            if best is None or item.confidence > best.confidence:
                best = item

    if best is None or best.confidence < 0.85:
        return None

    return CommandRequest(
        raw_text=text,
        intent=best.intent,
        confidence=best.confidence,
        params=dict(best.params) if best.params else {},
        language="en",
        classifier_source="instant_fast_lane",
    )

