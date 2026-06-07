"""Phase 189 — beta result feedback funnel tests.

Covers: useful=true/false submission, empty comment, secret redaction,
source-code is never stored, unauthenticated safety, and the admin inbox
not exposing secrets. Also asserts the frontend funnel wiring is present.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from jarvis_desktop import api, data_paths, operations


@pytest.fixture(autouse=True)
def _temp_data_dir(tmp_path, monkeypatch):
    """Point desktop data dir (feedback store) at an isolated temp dir."""
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    data_paths.reset_desktop_data_dir_cache()
    yield
    data_paths.reset_desktop_data_dir_cache()


def _feedback_rows():
    path = Path(operations._feedback_path())
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# ── Submission ───────────────────────────────────────────────────────────────

def test_useful_true_submission_is_stored():
    res = api.submit_result_feedback({"workflow": "change_plan", "useful": True})
    assert res["ok"] is True
    assert res["useful"] is True
    rows = _feedback_rows()
    assert len(rows) == 1
    assert rows[0]["kind"] == "result_feedback"
    assert rows[0]["workflow"] == "change_plan"
    assert rows[0]["useful"] is True


def test_useful_false_submission_is_stored():
    res = api.submit_result_feedback({"workflow": "debug", "useful": False, "category": "too_generic"})
    assert res["ok"] is True
    assert res["useful"] is False
    rows = _feedback_rows()
    assert rows[0]["useful"] is False
    assert rows[0]["category"] == "too_generic"


def test_optional_comment_may_be_empty():
    res = api.submit_result_feedback({"workflow": "what_breaks", "useful": True, "comment": ""})
    assert res["ok"] is True
    rows = _feedback_rows()
    assert rows[0]["comment"] == ""


def test_all_result_workflows_accepted():
    for wf in ("understanding", "what_breaks", "change_plan", "debug", "export"):
        res = api.submit_result_feedback({"workflow": wf, "useful": True})
        assert res["ok"] is True, wf


def test_unknown_workflow_rejected():
    res = api.submit_result_feedback({"workflow": "marketing", "useful": True})
    assert res["ok"] is False
    assert _feedback_rows() == []


def test_missing_useful_rejected():
    res = api.submit_result_feedback({"workflow": "debug"})
    assert res["ok"] is False
    assert _feedback_rows() == []


def test_invalid_category_coerced_to_other():
    res = api.submit_result_feedback({"workflow": "debug", "useful": True, "category": "nonsense"})
    assert res["ok"] is True
    assert _feedback_rows()[0]["category"] == "other"


# ── Redaction / privacy ──────────────────────────────────────────────────────

def test_secrets_redacted_from_comment():
    secret_comment = (
        "My key is sk-ant-api03-SECRETVALUE1234567890 and token eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYSJ9.sig "
        "and api_key=supersecretkey and path C:\\Users\\dana\\repo\\secret.py and github ghp_ABCDEFGHabcdefgh1234567890"
    )
    res = api.submit_result_feedback({"workflow": "debug", "useful": False, "comment": secret_comment})
    assert res["ok"] is True
    stored = _feedback_rows()[0]["comment"]
    assert "sk-ant-api03-SECRETVALUE1234567890" not in stored
    assert "eyJhbGciOiJIUzI1NiJ9" not in stored
    assert "supersecretkey" not in stored
    assert "ghp_ABCDEFGHabcdefgh1234567890" not in stored
    assert "C:\\Users\\dana" not in stored
    assert "[REDACTED]" in stored or "[path-redacted]" in stored or "[secret-redacted]" in stored


def test_source_code_not_stored():
    """Only safe fields are persisted — never source, repo files, or paths."""
    api.submit_result_feedback({
        "workflow": "change_plan",
        "useful": True,
        "comment": "def transfer_funds(a, b): return a - b  # business logic",
    })
    row = _feedback_rows()[0]
    allowed = {
        "feedback_id", "kind", "product", "workflow", "useful", "category",
        "message", "comment", "user_id", "email", "repo_metadata",
        "version", "build_commit", "installation_id", "timestamp",
    }
    assert set(row.keys()) <= allowed, f"unexpected fields: {set(row.keys()) - allowed}"
    # repo_metadata holds only safe counts — no paths/source keys.
    meta = row.get("repo_metadata") or {}
    assert set(meta.keys()) <= {
        "file_count", "module_count", "subsystem_count", "dependency_edges", "graph_quality",
    }
    blob = json.dumps(row).lower()
    for forbidden in ("password", "refresh_hash", "access_token", "/src/", "secret.py", "jwt_secret"):
        assert forbidden not in blob


def test_unauthenticated_submission_is_safe():
    """No signed account state present -> no user_id/email leaked, still ok."""
    res = api.submit_result_feedback({"workflow": "export", "useful": True})
    assert res["ok"] is True
    row = _feedback_rows()[0]
    assert row["user_id"] == ""
    assert row["email"] == ""


def test_authenticated_identity_attached(monkeypatch):
    monkeypatch.setattr(
        api_accounts_client(),
        "cached_identity",
        lambda: {"authenticated": True, "user_id": "u-123", "email": "beta@example.com"},
    )
    res = api.submit_result_feedback({"workflow": "debug", "useful": True})
    assert res["ok"] is True
    row = _feedback_rows()[0]
    assert row["user_id"] == "u-123"
    assert row["email"] == "beta@example.com"


def api_accounts_client():
    from jarvis_desktop import accounts_client
    return accounts_client


# ── Admin inbox ──────────────────────────────────────────────────────────────

def test_admin_inbox_requires_admin(monkeypatch):
    monkeypatch.delenv("ATLAS_ADMIN", raising=False)
    api.submit_result_feedback({"workflow": "debug", "useful": True})
    res = api.operations_result_feedback_inbox()
    assert res["ok"] is False
    assert res["code"] == "admin_disabled"


def test_admin_inbox_lists_feedback_without_secrets(monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    api.submit_result_feedback({
        "workflow": "what_breaks",
        "useful": False,
        "category": "missing_context",
        "comment": "leak api_key=supersecretkey token eyJhbGciOiJIUzI1NiJ9.eyJhIjoxfQ.sig",
    })
    res = api.operations_result_feedback_inbox()
    assert res["ok"] is True
    assert res["total"] == 1
    assert res["useful_no"] == 1
    item = res["items"][0]
    assert item["workflow"] == "what_breaks"
    assert item["useful"] is False
    assert item["category"] == "missing_context"
    # Comment is redacted; no secret-like fields anywhere in the inbox payload.
    assert "supersecretkey" not in json.dumps(res)
    assert "eyJhbGciOiJIUzI1NiJ9" not in json.dumps(res)
    blob = json.dumps(res).lower()
    for forbidden in ("password_hash", "refresh_hash", "access_token", "refresh_token", "jwt_secret"):
        assert forbidden not in blob


def test_admin_inbox_only_returns_result_feedback(monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    # A general feedback row should not appear in the result-feedback inbox.
    api.submit_feedback({"category": "general", "message": "general note here"})
    api.submit_result_feedback({"workflow": "debug", "useful": True})
    res = api.operations_result_feedback_inbox()
    assert res["total"] == 1
    assert res["items"][0]["workflow"] == "debug"


# ── Frontend funnel wiring ───────────────────────────────────────────────────

STATIC = Path(__file__).resolve().parents[1] / "static"


def test_frontend_funnel_present_in_atlas_beta_js():
    js = (STATIC / "atlas_beta.js").read_text(encoding="utf-8")
    assert "Was this useful?" in js
    assert "function resultFeedbackVote" in js
    assert "function resultFeedbackSend" in js
    assert "/api/feedback/result" in js
    assert "What worked or what was missing?" in js
    for cat in ("accurate", "missing_context", "too_generic", "wrong_repo_area",
                "hard_to_understand", "saved_time", "other"):
        assert cat in js


def test_frontend_slots_present_in_index_html():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="understandingFeedbackSlot"' in html
    assert 'id="exportFeedbackSlot"' in html


def test_admin_html_has_result_feedback_section():
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    assert "Result feedback" in html
    assert "/api/operations/result-feedback" in html
    assert 'id="resultFeedbackRows"' in html
    # No secret/hash columns in the result feedback section.
    section = html[html.find("Result feedback"):]
    import re
    assert not re.search(r"password_hash|refresh_hash|refresh_token|access_token|jwt_secret", section, re.IGNORECASE)
