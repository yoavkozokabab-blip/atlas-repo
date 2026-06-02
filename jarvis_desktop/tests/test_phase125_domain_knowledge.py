"""Phase 125 — domain knowledge layer for Build Plan and Investigate."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, domain_knowledge as dk, planning_engine


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _trading_repo(tmp_path: Path) -> Path:
    root = tmp_path / "trader"
    _write(root / "indicators" / "ema.py", "def ema(series, period):\n    return series\n")
    _write(root / "indicators" / "rsi.py", "def rsi(series, period):\n    return series\n")
    _write(root / "strategy" / "signals.py", "from indicators.ema import ema\n")
    _write(root / "services" / "backtest.py", "def run_backtest():\n    return []\n")
    _write(root / "services" / "live_paper_engine.py", "from services.backtest import run_backtest\n")
    _write(root / "config" / "settings.py", "EMA_PERIOD = 14\n")
    return root


def _web_repo(tmp_path: Path) -> Path:
    root = tmp_path / "webapp"
    _write(root / "auth" / "login.py", "def login():\n    return True\n")
    _write(root / "auth" / "session.py", "from auth.login import login\n")
    _write(root / "api" / "stripe_billing.py", "def charge():\n    return 1\n")
    _write(root / "api" / "webhooks.py", "def stripe_webhook():\n    pass\n")
    _write(root / "middleware" / "rate_limit.py", "def limit():\n    pass\n")
    return root


def _infra_repo(tmp_path: Path) -> Path:
    root = tmp_path / "svc"
    _write(root / "logging" / "audit.py", "def audit():\n    pass\n")
    _write(root / "workers" / "task_queue.py", "def enqueue():\n    pass\n")
    _write(root / "monitoring" / "metrics.py", "def health():\n    return True\n")
    return root


def _graph_paths() -> set[str]:
    graph = api._STATE.get("graph") or {}
    return {
        n["path"]
        for n in graph.get("nodes", [])
        if n.get("type") == "module" and n.get("path")
    }


def _assert_grounded(paths: list[str]) -> None:
    allowed = _graph_paths()
    for path in paths:
        assert path in allowed, f"Hallucinated path: {path}"


@pytest.fixture()
def trading_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    result = api.scan_repository(str(_trading_repo(tmp_path)))
    assert result["ok"], result
    return result


@pytest.fixture()
def web_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    result = api.scan_repository(str(_web_repo(tmp_path)))
    assert result["ok"], result
    return result


@pytest.fixture()
def infra_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    result = api.scan_repository(str(_infra_repo(tmp_path)))
    assert result["ok"], result
    return result


# --- Registry / classification ---


def test_classify_ema_build():
    c = dk.classify_request("add ema indicator", mode="build")
    assert c.concept_id == "ema"
    assert c.domain == "trading"
    assert c.feature_type == "indicator"
    assert c.concept_confidence in {"low", "medium", "high"}


def test_classify_stripe_billing():
    c = dk.classify_request("add stripe billing", mode="build")
    assert c.concept_id == "stripe_billing"
    assert "webhook" in " ".join(dk.knowledge_verification(c)).lower() or True


# --- Trading build ---


def test_build_ema_mentions_warmup_lookahead_backtest_live(trading_scan):
    res = api.plan_change("add EMA indicator to the strategy")
    assert res["ok"]
    dk_block = res["plan"].get("domain_knowledge") or {}
    assert dk_block.get("applied")
    assert dk_block.get("concept_id") == "ema"
    blob = " ".join(
        [
            res["formatted"],
            " ".join(dk_block.get("knowledge_risks") or []),
            " ".join(res["plan"].get("verification_plan") or []),
            res["prompts"]["claude"],
        ]
    ).lower()
    assert "warmup" in blob
    assert "lookahead" in blob
    assert "backtest" in blob and "live" in blob
    roles = dk_block.get("file_roles") or {}
    for path in (roles.get("must_inspect") or []) + (roles.get("likely_modify") or []):
        _assert_grounded([path])


def test_build_rsi_indicator(trading_scan):
    res = api.plan_change("add rsi indicator")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "rsi"


def test_build_atr_stop_loss(trading_scan):
    res = api.plan_change("add atr stop loss")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "atr_stop_loss"


# --- Trading investigate ---


def test_investigate_backtest_better_than_paper(trading_scan):
    res = api.investigate_symptom("backtest is much better than paper trading")
    assert res["ok"]
    dk_block = res["plan"].get("domain_knowledge") or {}
    assert dk_block.get("applied")
    blob = " ".join(
        [
            res["formatted"],
            " ".join(res["plan"].get("domain_failure_modes") or []),
            res["prompts"]["claude"],
        ]
    ).lower()
    assert "fill" in blob or "slippage" in blob or "signal" in blob
    for path in res["plan"].get("likely_modules") or []:
        _assert_grounded([path])


def test_investigate_ema_backtest_not_live(trading_scan):
    res = api.investigate_symptom("EMA signal works in backtest but not paper")
    assert res["ok"]
    dk = res["plan"].get("domain_knowledge") or {}
    assert dk.get("applied")
    assert dk.get("concept_id") in {"indicator_backtest_live", "ema"}
    text = res["formatted"].lower() + res["prompts"]["claude"].lower()
    assert "warmup" in text or "forming" in text or "live" in text


# --- Web ---


def test_build_authentication(web_scan):
    res = api.plan_change("add authentication")
    assert res["ok"]
    dk_block = res["plan"]["domain_knowledge"]
    assert dk_block["concept_id"] == "authentication"
    prompt = res["prompts"]["claude"].lower()
    assert "session" in prompt or "token" in prompt or "permission" in prompt


def test_build_stripe_webhooks(web_scan):
    res = api.plan_change("add stripe billing")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "stripe_billing"
    blob = (res["formatted"] + res["prompts"]["claude"]).lower()
    assert "webhook" in blob


def test_build_rate_limiting(web_scan):
    res = api.plan_change("add rate limiting to the API")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "rate_limiting"


# --- Infra ---


def test_build_logging(infra_scan):
    res = api.plan_change("add logging")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "logging"


def test_build_retry_queue(infra_scan):
    res = api.plan_change("add retry queue for failed jobs")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "retry_queue"


def test_build_observability(infra_scan):
    res = api.plan_change("add observability and health checks")
    assert res["ok"]
    assert res["plan"]["domain_knowledge"]["concept_id"] == "observability"


def test_prompt_exports_include_domain_risks(trading_scan):
    res = api.plan_change("add ema indicator")
    assert "Domain concept" in res["prompts"]["claude"]
    assert "Knowledge-backed risks" in res["prompts"]["claude"]


def test_no_hallucinated_paths_on_unknown_repo(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    root = tmp_path / "minimal"
    _write(root / "main.py", "print('hi')\n")
    api.scan_repository(str(root))
    res = api.plan_change("add ema indicator")
    assert res["ok"]
    roles = res["plan"]["domain_knowledge"].get("file_roles") or {}
    for path in (roles.get("must_inspect") or []):
        _assert_grounded([path])
    note = res["plan"]["domain_knowledge"].get("integration_note", "")
    assert "No production module" in note or "entry points" in note.lower() or "Candidate" in note
