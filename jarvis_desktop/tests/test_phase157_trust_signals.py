"""Phase 157 — trust signals: evidence, confidence, and reason on every result.

Each Change Plan / Investigation / What-breaks result must show evidence
(files, symbols, references), a confidence level (high / medium / low), and a
reason explaining why Atlas believes the result. No intelligence is changed —
these tests assert the trust UI and that the engine already exposes the data.
"""

from __future__ import annotations

from pathlib import Path

from jarvis_desktop import api

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "jarvis_desktop" / "static"
TRUST = STATIC / "atlas_trust.js"
APP_JS = STATIC / "app.js"
STYLES = STATIC / "styles.css"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Trust block UI
# --------------------------------------------------------------------------- #
def test_trust_block_has_evidence_confidence_reason():
    js = _read(TRUST)
    assert "Why Atlas believes this" in js
    # Evidence: files, symbols, references
    assert "Files" in js and "Symbols" in js and "References" in js
    assert "tzEvidence" in js
    # Reason
    assert "tzReason" in js
    assert "trust-reason" in js
    # Confidence levels
    assert "high" in js and "medium" in js and "low" in js
    assert "conf-badge" in js


def test_confidence_normalizes_to_three_levels():
    js = _read(TRUST)
    assert "tzNormalizeConfidence" in js
    assert 'return "high"' in js
    assert 'return "low"' in js
    assert 'return "medium"' in js


def test_trust_block_wired_into_all_workflows():
    app = _read(APP_JS)
    assert 'trustBlock("build")' in app
    assert 'trustBlock("investigate")' in app
    assert 'trustBlock("impact")' in app


def test_confidence_badge_styles_exist():
    css = _read(STYLES)
    assert ".conf-badge" in css
    assert ".conf-high" in css
    assert ".conf-medium" in css
    assert ".conf-low" in css


# --------------------------------------------------------------------------- #
# SmartScreen / unsigned-beta first-launch guidance
# --------------------------------------------------------------------------- #
def test_unsigned_beta_notice_present():
    js = _read(TRUST)
    assert "Atlas is an unsigned application" in js
    assert "SmartScreen" in js
    assert "Run anyway" in js
    assert "showUnsignedAppNotice" in js


# --------------------------------------------------------------------------- #
# Engine already exposes confidence + evidence (no intelligence change)
# --------------------------------------------------------------------------- #
def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "trust_repo"
    (root / "services").mkdir(parents=True)
    (root / "api").mkdir()
    (root / "services" / "auth.py").write_text(
        "def login(user):\n    return True\n", encoding="utf-8"
    )
    (root / "services" / "logging_util.py").write_text(
        "def log(msg):\n    print(msg)\n", encoding="utf-8"
    )
    (root / "api" / "handlers.py").write_text(
        "from services.auth import login\nfrom services.logging_util import log\n"
        "def handle():\n    log('hi')\n    return login('x')\n",
        encoding="utf-8",
    )
    return root


def test_change_plan_exposes_confidence_and_evidence(tmp_path):
    api.scan_repository(str(_make_repo(tmp_path)))
    res = api.plan_change("add structured logging to API handlers")
    assert res["ok"], res
    plan = res["plan"]
    assert "confidence" in plan
    # Evidence is available in at least one grounded form.
    assert (
        plan.get("evidence")
        or plan.get("repository_evidence")
        or plan.get("implementation_order")
        or plan.get("files_to_inspect_first")
    )


def test_impact_exposes_confidence_and_evidence(tmp_path):
    api.scan_repository(str(_make_repo(tmp_path)))
    res = api.change_impact_simulation("services/auth.py")
    assert res["ok"], res
    assert "confidence" in res
    assert "risk_level" in res
    # Importers / direct impact form the evidence/references.
    assert "direct_impact" in res
