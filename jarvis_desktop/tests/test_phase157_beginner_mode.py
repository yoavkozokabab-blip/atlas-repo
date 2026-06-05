"""Phase 157 — beginner / advanced output simplification.

Beginner view shows plain English; Advanced view shows full details. The
toggle is in the top bar, persists, and drives `.advanced-only` /
`.beginner-only` visibility. UI-only.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "jarvis_desktop" / "static"
INDEX = STATIC / "index.html"
TRUST = STATIC / "atlas_trust.js"
APP_JS = STATIC / "app.js"
STYLES = STATIC / "styles.css"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_mode_toggle_present_in_topbar():
    html = _read(INDEX)
    assert 'id="modeToggle"' in html
    assert "setOutputMode('beginner')" in html
    assert "setOutputMode('advanced')" in html


def test_body_defaults_to_beginner_mode():
    html = _read(INDEX)
    assert 'class="mode-beginner"' in html
    assert 'src="atlas_trust.js"' in html


def test_output_mode_logic_in_trust_js():
    js = _read(TRUST)
    assert "OUTPUT_MODE_KEY" in js
    assert "getOutputMode" in js
    assert "applyOutputMode" in js
    assert "setOutputMode" in js
    assert "beginner" in js and "advanced" in js


def test_mode_visibility_css_rules():
    css = _read(STYLES)
    assert "body.mode-beginner .advanced-only" in css
    assert "body.mode-advanced .beginner-only" in css


def test_advanced_only_blocks_tagged_in_outputs():
    app = _read(APP_JS)
    # Technical detail blocks (raw markdown, prompt previews, deep evidence) are
    # advanced-only so beginners see plain English.
    assert app.count("advanced-only") >= 3


def test_trust_block_has_beginner_and_advanced_layers():
    js = _read(TRUST)
    assert "beginner-only" in js
    assert "advanced-only" in js
