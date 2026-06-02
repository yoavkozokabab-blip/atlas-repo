"""Phase 129 — Repository Evidence Engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api
from jarvis_desktop.evidence_engine import EvidenceStore, analyze_concept, build_evidence_store
from jarvis_desktop.evidence_engine.ast_scanner import scan_python_source


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _evidence_repo(tmp_path: Path) -> Path:
    root = tmp_path / "algo_scanner"
    _write(
        root / "models" / "sma.py",
        "class SMAIndicator:\n    def compute(self, bars):\n        return bars\n",
    )
    _write(
        root / "models" / "indicator_registry.py",
        "class SignalRegistry:\n    def register_indicator(self, name, cls):\n        pass\n",
    )
    _write(
        root / "services" / "http_client.py",
        "import time\n\ndef fetch(url):\n    for attempt in range(3):\n        try:\n            return url\n        except Exception:\n            time.sleep(2 ** attempt)\n",
    )
    _write(
        root / "middleware" / "request_logging.py",
        "def request_id_middleware(environ, start_response):\n    request_id = environ.get('HTTP_X_REQUEST_ID', 'local')\n    return start_response('200 OK', [('X-Request-ID', request_id)])\n",
    )
    _write(
        root / "config" / "feature_flags.py",
        "FEATURE_EMA = False\nFEATURE_TRACING = True\n",
    )
    _write(
        root / "auth" / "middleware.py",
        "def authenticate_jwt(token):\n    return token is not None\n",
    )
    _write(
        root / "trading" / "backtest_config.py",
        "SLIPPAGE = 0.001\nFILL_MODEL = 'ideal'\n",
    )
    _write(
        root / "trading" / "paper_config.py",
        "SLIPPAGE = 0.01\nFILL_MODEL = 'broker'\n",
    )
    return root


@pytest.fixture()
def evidence_scan(tmp_path):
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "scan_cache": {},
        }
    )
    root = _evidence_repo(tmp_path)
    result = api.scan_repository(str(root))
    assert result["ok"], result
    assert api._STATE.get("evidence_store")
    return root


def test_ast_scanner_finds_symbols():
    src = "class SMAIndicator:\n    def compute(self):\n        return 1\n"
    scan = scan_python_source("models/sma.py", src)
    names = {s.name for s in scan.symbols}
    assert "SMAIndicator" in names
    assert "compute" in names


def test_evidence_store_built_on_scan(evidence_scan):
    store_raw = api._STATE["evidence_store"]
    assert store_raw.get("symbol_index", {}).get("symbol_count", 0) >= 8


def test_ema_finds_indicator_insertion(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="ema", concept_name="EMA", category="indicator", domain="trading")
    assert bundle.status in ("Partially Implemented", "Implemented")
    assert any("SMA" in f or "register" in f.lower() for f in bundle.found)
    assert any("ema" in m.lower() or "exponential" in m.lower() for m in bundle.missing)
    assert "indicator_registry" in bundle.recommended_insertion
    assert bundle.confidence_score >= 40


def test_circuit_breaker_finds_http_boundary(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="circuit_breaker", concept_name="Circuit Breaker")
    assert any("http" in f.lower() or "retry" in f.lower() or "fetch" in f.lower() for f in bundle.found)
    assert "http_client" in bundle.recommended_insertion
    assert bundle.status == "Partially Implemented"


def test_tracing_finds_middleware_logging(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="distributed_tracing", concept_name="Distributed Tracing")
    assert any("request" in f.lower() or "logging" in f.lower() for f in bundle.found)
    assert "middleware" in bundle.recommended_insertion


def test_retry_finds_retry_loop(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="retry_backoff", concept_name="Retry with Backoff")
    assert any(
        "retry" in f.lower() or "attempt" in f.lower() or "sleep" in f.lower() or "fetch" in f.lower()
        for f in bundle.found
    )
    assert bundle.status in ("Partially Implemented", "Implemented")


def test_feature_flags_find_config(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="feature_flags", concept_name="Feature Flags")
    assert any("feature" in f.lower() or "FEATURE" in f for f in bundle.found)
    assert "feature_flags" in bundle.recommended_insertion


def test_authentication_finds_auth_boundary(evidence_scan):
    store = EvidenceStore.from_dict(api._STATE["evidence_store"])
    bundle = analyze_concept(store, concept_id="jwt", concept_name="JWT", category="authentication", domain="security")
    assert any("jwt" in f.lower() or "auth" in f.lower() for f in bundle.found)
    assert "auth" in bundle.recommended_insertion


def test_build_plan_includes_repository_evidence(evidence_scan):
    res = api.plan_change("add EMA indicator with configurable period")
    assert res["ok"]
    rev = res["plan"].get("repository_evidence") or {}
    assert rev.get("status")
    assert rev.get("confidence_score", 0) >= 40
    assert "REPOSITORY EVIDENCE" in res["formatted"]
    assert rev.get("recommended_insertion")


def test_investigate_backtest_evidence_backed(evidence_scan):
    res = api.investigate_symptom("backtest is much better than paper trading")
    assert res["ok"]
    rev = res["plan"].get("repository_evidence") or {}
    assert rev.get("found")
    assert any("slippage" in f.lower() for f in rev["found"])
    assert "Repository evidence" in res["formatted"] or "slippage" in res["formatted"].lower()


def test_mapping_prefers_evidence_over_path_only(evidence_scan):
    res_path = api.plan_change("Add circuit breaker for outbound HTTP")
    assert res_path["ok"]
    insertion = (res_path["plan"].get("repository_evidence") or {}).get("recommended_insertion") or ""
    assert "http_client" in insertion
    inspect = res_path["plan"].get("files_to_inspect_first") or []
    assert inspect[0] == insertion or insertion in inspect[:2]
