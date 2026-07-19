"""Regression coverage for pre-answer Not Found Confidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def indexed_repository(tmp_path: Path):
    root = tmp_path / "repo"
    _write(
        root / "billing" / "payments.py",
        "class PaymentProcessor:\n"
        "    def charge(self):\n"
        "        return True\n\n"
        "def reconcile_payments():\n"
        "    return True\n",
    )
    _write(root / "handlers" / "http.py", "def handler():\n    return 'http'\n")
    _write(root / "handlers" / "events.py", "def handler():\n    return 'event'\n")
    _write(root / "settings.py", "FEATURE_BILLING_CONFIG = True\n")
    _write(root / "deploy" / "staging.yaml", "service: atlas\n")
    api._STATE.update({
        "path": None,
        "scan": None,
        "graph": None,
        "index": None,
        "risks": None,
        "evidence_store": None,
        "demo_mode": False,
        "scan_cache": {},
    })
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


def _assert_not_found(result: dict, entity: str) -> None:
    assert result["ok"] is True
    assert result["mode"] == "not_found"
    assert result["answer"].startswith(
        f"I couldn't find evidence that {entity} exists in this repository."
    )
    assert "Searched:" in result["answer"]
    assert result["searched"]
    assert result["evidence"] == result["searched"]
    assert result["confidence"] == "low"
    assert result["copy_targets"] == {"claude": "", "codex": "", "cursor": ""}
    assert "repository summary" not in result["answer"].lower()
    assert "high confidence" not in result["answer"].lower()


def test_missing_class_stops_before_repository_summary(indexed_repository):
    result = api.copilot_ask("Where is class GhostPaymentProcessor defined?")
    _assert_not_found(result, "GhostPaymentProcessor")
    assert result["entity_check"]["expected_kind"] == "class"
    assert any(item["name"] == "PaymentProcessor" for item in result["similar"])


def test_missing_function_stops_before_repository_summary(indexed_repository):
    result = api.copilot_ask("How does function reconcile_invoices work?")
    _assert_not_found(result, "reconcile_invoices")
    assert result["entity_check"]["expected_kind"] == "function"
    assert any(item["name"] == "reconcile_payments" for item in result["similar"])


def test_missing_config_stops_before_repository_summary(indexed_repository):
    result = api.copilot_ask("Where is config PAYMENT_GATEWAY_URL configured?")
    _assert_not_found(result, "PAYMENT_GATEWAY_URL")
    assert "config" in result["entity_check"]["expected_kind"]


def test_missing_deployment_file_stops_before_repository_summary(indexed_repository):
    result = api.copilot_ask("What does deploy/production.yaml do?")
    _assert_not_found(result, "deploy/production.yaml")
    assert result["entity_check"]["expected_kind"] == "file"
    assert any(item["path"] == "deploy/staging.yaml" for item in result["similar"])


def test_nonsense_query_is_not_turned_into_repository_summary(indexed_repository):
    result = api.copilot_ask("florbledy snargle")
    _assert_not_found(result, "florbledy snargle")
    assert result["entity_check"]["source"] == "unknown_phrase"


def test_ambiguous_query_requires_unique_direct_evidence(indexed_repository):
    result = api.copilot_ask("How does handler work?")
    _assert_not_found(result, "handler as a unique entity")
    assert result["entity_check"]["status"] == "ambiguous"
    assert {item["path"] for item in result["similar"]} == {
        "handlers/events.py",
        "handlers/http.py",
    }
    assert "fully-qualified symbol" in result["suggested_action"]


def test_existing_class_has_direct_support_before_high_confidence(indexed_repository):
    result = api.copilot_ask("Where is class PaymentProcessor defined?")
    assert result["mode"] == "location"
    assert result["entity_check"]["status"] == "found"
    assert any("class `PaymentProcessor`" in item for item in result["evidence"])
    assert "billing/payments.py" in result["files"]


def test_high_confidence_is_withheld_without_attached_direct_evidence():
    result = api._copilot_envelope("test", "Unsupported answer", confidence="high")
    assert result["confidence"] == "medium"
    assert any("High confidence was withheld" in item for item in result["limitations"])

