"""Beta1 release gate: feedback must be delivered or honestly reported.

Before this release the desktop feedback form wrote a local JSONL file and told
the user the report was saved, while `ATLAS_FEEDBACK_URL` was never set in any
packaged build — so nothing ever reached the product owner. The same was true
of `ATLAS_UPDATE_CHECK_URL`: an installed Atlas could never learn about a fix.

These tests pin the three properties that matter: packaged builds have both
endpoints by default, a failed send never claims success and never loses the
local copy, and the update check stays safe when the network is gone.
"""
from __future__ import annotations

import json
import os
import urllib.error
from typing import Any, Dict

import pytest

from atlas_desktop import product_info


class _Resp:
    def __init__(self, status: int = 200, payload: Dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload or {}

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self) -> int:
        return self.status

    def close(self) -> None:
        pass

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *_: object) -> None:
        pass


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ATLAS_FEEDBACK_URL", "ATLAS_UPDATE_CHECK_URL", "ATLAS_WEB_URL"):
        monkeypatch.delenv(name, raising=False)


# --- packaged defaults -----------------------------------------------------

def test_source_runs_stay_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dev checkout must not silently post to production."""
    monkeypatch.setattr(product_info.sys, "frozen", False, raising=False)
    assert product_info.feedback_url() == ""
    assert product_info.update_check_url() == ""


def test_packaged_builds_get_both_endpoints_without_any_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(product_info.sys, "frozen", True, raising=False)
    from atlas_desktop import accounts_client

    base = accounts_client.web_base()
    assert product_info.feedback_url() == f"{base}/api/feedback"
    assert product_info.update_check_url() == f"{base}/api/update/windows"


def test_explicit_env_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(product_info.sys, "frozen", True, raising=False)
    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://collector.example.test/f")
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://collector.example.test/u")
    assert product_info.feedback_url() == "https://collector.example.test/f"
    assert product_info.update_check_url() == "https://collector.example.test/u"


# --- update check ----------------------------------------------------------

def test_update_check_survives_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example.test/manifest")
    monkeypatch.setattr(
        product_info.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("offline")),
    )
    result = product_info.check_for_update()
    assert result["ok"] is True
    assert result["update_available"] is False
    assert result["check_failed"] is True


def test_update_check_reads_the_manifest_this_release_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shape must match websites/atlas-web/app/api/update/windows/route.ts."""
    manifest = {
        "latestVersion": "1.0.7",
        "version": "1.0.7",
        "downloadUrl": "https://example.test/Atlas-Setup-1.0.7.exe",
        "sha256": "A" * 64,
        "mandatory": False,
        "release_notes_url": "https://example.test/releases/tag/v1.0.7",
    }
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example.test/manifest")
    monkeypatch.setattr(product_info.urllib.request, "urlopen", lambda *a, **k: _Resp(200, manifest))
    result = product_info.check_for_update()
    assert result["update_available"] is True
    assert result["latest_version"] == "1.0.7"
    assert result["release_notes_url"] == "https://example.test/releases/tag/v1.0.7"


def test_update_check_never_returns_an_executable_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Atlas offers a URL; it must never hand back something to auto-execute."""
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example.test/manifest")
    monkeypatch.setattr(
        product_info.urllib.request, "urlopen",
        lambda *a, **k: _Resp(200, {"version": "1.0.7", "downloadUrl": "https://example.test/x.exe"}),
    )
    result = product_info.check_for_update()
    assert "installer_path" not in result
    assert "download_url" not in result


def test_update_request_carries_no_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The manifest is a bare GET: no install id, no repo, no machine data."""
    captured: Dict[str, Any] = {}

    def fake_urlopen(req, timeout=5):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data
        captured["headers"] = dict(req.headers)
        return _Resp(200, {"version": product_info.PRODUCT_VERSION})

    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example.test/manifest")
    monkeypatch.setattr(product_info.urllib.request, "urlopen", fake_urlopen)
    product_info.check_for_update()

    assert captured["method"] == "GET"
    assert captured["body"] is None
    assert "?" not in captured["url"], "no query string may carry identifiers"
    assert not any("atlas" in key.lower() for key in captured["headers"]), captured["headers"]


# --- feedback delivery -----------------------------------------------------

def _submit(monkeypatch: pytest.MonkeyPatch, tmp_path, *, urlopen) -> Dict[str, Any]:
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    from atlas_desktop import api, data_paths

    data_paths.reset_desktop_data_dir_cache()
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return api.submit_feedback({"category": "bug", "message": "Impact missed a dependent module."})


def test_successful_delivery_says_sent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example.test/api/feedback")
    result = _submit(monkeypatch, tmp_path, urlopen=lambda *a, **k: _Resp(201, {"ok": True}))
    assert result["ok"] is True
    assert result["remote_sent"] is True
    assert result["destination"] == "remote"
    assert "sent" in result["message"].lower()


def test_failed_delivery_never_claims_success_and_keeps_the_local_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example.test/api/feedback")

    def boom(*_a, **_k):
        raise urllib.error.URLError("unreachable")

    result = _submit(monkeypatch, tmp_path, urlopen=boom)
    assert result["remote_sent"] is False
    assert result["destination"] == "local_after_remote_fail"
    message = result["message"].lower()
    assert "not sent" in message, result["message"]
    assert product_info.support_email() in result["message"], "must name where to send it instead"

    stored = (tmp_path / "feedback" / "feedback.jsonl").read_text(encoding="utf-8").strip()
    assert "Impact missed a dependent module." in stored


def test_local_copy_survives_a_delivery_crash(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The write happens before the send, so even a hard failure keeps the text."""

    def explode(*_a, **_k):
        raise OSError("socket died")

    result = _submit(monkeypatch, tmp_path, urlopen=explode)
    assert result["remote_sent"] is False
    assert (tmp_path / "feedback" / "feedback.jsonl").exists()


def test_payload_carries_no_repository_or_path_data(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: Dict[str, Any] = {}

    def capture(req, timeout=5):  # noqa: ANN001
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(201, {"ok": True})

    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example.test/api/feedback")
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    from atlas_desktop import api, data_paths

    data_paths.reset_desktop_data_dir_cache()
    monkeypatch.setattr("urllib.request.urlopen", capture)
    api.submit_feedback({
        "category": "bug",
        "message": r"Broke on C:\Users\alice\secret-repo\app.py with api_key=LEAKME",
    })

    body = captured["body"]
    blob = json.dumps(body)
    assert "C:\\Users\\alice" not in blob
    assert "LEAKME" not in blob
    assert "[path-redacted]" in body["message"]
    assert set(body) <= {
        "feedback_id", "product", "category", "message", "email", "page",
        "version", "build_commit", "installation_id", "diagnostics_summary", "timestamp",
    }, sorted(body)


def test_feedback_id_is_stable_enough_for_server_deduplication(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    seen: list[str] = []

    def capture(req, timeout=5):  # noqa: ANN001
        seen.append(json.loads(req.data.decode("utf-8"))["feedback_id"])
        return _Resp(201, {"ok": True})

    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example.test/api/feedback")
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    from atlas_desktop import api, data_paths

    data_paths.reset_desktop_data_dir_cache()
    monkeypatch.setattr("urllib.request.urlopen", capture)
    api.submit_feedback({"category": "bug", "message": "one"})
    api.submit_feedback({"category": "bug", "message": "two"})

    assert len(set(seen)) == 2, "distinct reports must not collide on the server"
    for value in seen:
        assert 4 <= len(value) <= 80 and value.replace("-", "").isalnum()


# --- version consistency ---------------------------------------------------

def test_mcp_reports_the_product_version(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas_desktop.mcp_server import runtime

    assert runtime.ATLAS_MCP_VERSION == product_info.PRODUCT_VERSION


def test_release_version_is_the_beta_identity() -> None:
    assert product_info.PRODUCT_VERSION == "1.0.6-beta.1"
    assert product_info.LAUNCH_BUILD_LABEL.endswith(product_info.PRODUCT_VERSION)
