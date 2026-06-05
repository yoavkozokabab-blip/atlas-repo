"""Phase 158 — No domain leakage tests.

Verifies that trading/EMA concepts do not bleed into unrelated domains.
Also verifies domain routing accuracy for common non-trading symptoms.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from jarvis_desktop import planning_engine as pe


def _make_ctx(paths=None, with_trading=False):
    if with_trading:
        paths = paths or ["trading/strategy.py", "indicators/ema.py", "backtest/engine.py"]
    else:
        paths = paths or [
            "api/routes.py", "services/auth.py", "core/hub.py",
            "dispatch/event.py", "listeners/handler.py",
        ]
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p,
         "fan_in": 3, "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}]
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "test_repo",
        "entry_points": [],
        "scan": {},
    }


LEAKAGE_CASES = [
    ("why are duplicate events being fired", "duplicate events → NOT ema"),
    ("websocket events duplicate", "websocket events → NOT trading"),
    ("add rate limiting to the API", "rate limiting build → NOT trading"),
    ("authentication is broken", "auth broken → NOT trading"),
    ("memory leak in the worker", "memory leak → NOT trading"),
    ("the dashboard shows wrong metrics", "dashboard mismatch → NOT trading"),
]


@pytest.mark.parametrize("prompt,label", LEAKAGE_CASES)
def test_no_trading_leakage_non_trading_repo(prompt, label):
    """Non-trading repo: trading/EMA must not appear in results for non-trading prompts."""
    ctx = _make_ctx()
    if "add " in prompt or "implement " in prompt or "build " in prompt:
        result = pe.plan_change(prompt, ctx)
    else:
        result = pe.investigate_symptom(prompt, ctx)
    assert result["ok"] is True, f"[{label}] Expected ok=True, got error"
    plan = result.get("plan") or {}
    dk = plan.get("domain_knowledge") or {}
    assert dk.get("domain") != "trading", (
        f"[{label}] Trading domain leaked into non-trading context: {dk.get('domain')}"
    )
    assert dk.get("concept_id") != "ema", (
        f"[{label}] EMA concept leaked: {dk.get('concept_id')}"
    )
    # Also check that no trading-specific failure modes appear
    fms = dk.get("domain_failure_modes") or dk.get("failure_modes") or []
    for fm in fms:
        assert "slippage" not in fm.lower(), f"[{label}] slippage in failure modes: {fm}"
        assert "backtest" not in fm.lower() or "test" in prompt.lower(), (
            f"[{label}] backtest in failure modes for non-trading symptom: {fm}"
        )


def test_duplicate_events_routes_to_pub_sub():
    """Duplicate events must route to pub_sub concept, not trading."""
    ctx = _make_ctx()
    result = pe.investigate_symptom("why are duplicate events being fired", ctx)
    assert result["ok"] is True
    plan = result["plan"]
    dk = plan.get("domain_knowledge") or {}
    # If concept is set, it should be pub_sub (messaging), not ema
    concept = dk.get("concept_id") or ""
    assert concept != "ema"
    if concept:
        assert "pub_sub" in concept or "messaging" in dk.get("domain", ""), (
            f"Duplicate events should route to pub_sub, not {concept}"
        )


def test_rate_limiting_routes_to_rate_limiting():
    """Rate limiting build plan routes to rate_limiting concept."""
    ctx = _make_ctx(["api/routes.py", "middleware/throttle.py", "http/handler.py"])
    result = pe.plan_change("add rate limiting", ctx)
    assert result["ok"] is True
    plan = result["plan"]
    assert plan.get("intent") == "rate_limiting", (
        f"Expected rate_limiting intent, got {plan.get('intent')}"
    )


def test_trading_leakage_blocked_on_symbol_match():
    """EMA symbol in user text must not leak to non-trading repo (word boundary)."""
    ctx = _make_ctx(["services/schema.py", "api/streaming.py"])  # no trading files
    # 'streaming' contains substring 'ema' in ... 'schema' - ensure word boundary works
    result = pe.investigate_symptom("schema validation is failing", ctx)
    assert result["ok"] is True
    plan = result["plan"]
    dk = plan.get("domain_knowledge") or {}
    assert dk.get("concept_id") != "ema", (
        "'schema' must not trigger EMA (substring match leak)"
    )


def test_trading_allowed_on_trading_repo():
    """When repo contains trading files and user asks trading question, allow it."""
    trading_ctx = _make_ctx(with_trading=True)
    result = pe.investigate_symptom(
        "backtest results differ from live trading", trading_ctx
    )
    assert result["ok"] is True
    # No assertion on domain — just must not crash or return error


def test_repo_has_trading_evidence_detection():
    """_repo_has_trading_evidence detects trading paths correctly."""
    from jarvis_desktop.planning_engine import _repo_has_trading_evidence

    trading_ctx = _make_ctx(with_trading=True)
    assert _repo_has_trading_evidence(trading_ctx) is True

    plain_ctx = _make_ctx()
    assert _repo_has_trading_evidence(plain_ctx) is False


def test_request_mentions_trading_explicitly():
    """_request_mentions_trading_explicitly correctly classifies requests."""
    from jarvis_desktop.planning_engine import _request_mentions_trading_explicitly

    assert _request_mentions_trading_explicitly("add rate limiting") is False
    assert _request_mentions_trading_explicitly("why are events duplicated") is False
    assert _request_mentions_trading_explicitly("ema calculation wrong") is True
    assert _request_mentions_trading_explicitly("backtest differs from live") is True
    assert _request_mentions_trading_explicitly("position sizing is wrong") is True
    assert _request_mentions_trading_explicitly("signals are NaN in backtest") is True
    # 'streaming' does not trigger EMA (schema contains 'ema' substring)
    assert _request_mentions_trading_explicitly("schema validation failing") is False
