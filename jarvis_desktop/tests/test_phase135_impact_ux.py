"""Phase 135 — Impact UX polish (presentation-only) contract tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

STATIC = Path(__file__).resolve().parents[1] / "static"
APP = (STATIC / "app.js").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")


class TestSummaryCards:
    def test_helper_functions_exist(self):
        for fn in ("function impactSemanticCard", "function impactBlastCard",
                   "function impactArchSummary", "function impactModuleTags"):
            assert fn in APP, fn

    def test_semantic_card_fields(self):
        block = APP[APP.index("function impactSemanticCard"):APP.index("function impactBlastCard")]
        assert "semantic_label" in block
        assert "resolved_modules" in block
        assert "resolved_symbols" in block
        assert "confidence" in block
        assert "Key symbols" in block

    def test_blast_card_fields(self):
        block = APP[APP.index("function impactBlastCard"):APP.index("function _humanList")]
        assert "architectural_blast_radius" in block
        assert "direct importers" in block
        assert "transitive impact" in block

    def test_arch_summary_sentence(self):
        block = APP[APP.index("function impactArchSummary"):]
        block = block[: block.index("}\n\n") + 1] if "}\n\n" in block else block[:1500]
        assert "subsystems_impacted" in block or "affected_subsystems" in block
        assert "runtime boundary" in block
        assert "Blast radius" in block


class TestFileListCapping:
    def test_module_tags_capped_with_show_all(self):
        block = APP[APP.index("function impactModuleTags"):APP.index("function impactSemanticCard")]
        assert "slice(0, n)" in block
        assert "Show all" in block and "impacted modules" in block
        assert "<details" in block  # collapsible


class TestCardOrder:
    def test_cards_above_file_lists_in_order(self):
        run = APP[APP.index("async function runImpact"):APP.index("function impactInspect")]
        order = [
            run.index("impactSemanticCard(r)"),
            run.index("impactBlastCard(r)"),
            run.index("impactArchSummary(r)"),
            run.index("Direct impact"),
            run.index("Indirect impact"),
            run.index("Tests to run"),
            run.index("Safe rollback"),
        ]
        assert order == sorted(order), "cards must precede file lists in the documented order"


class TestCopilotImpactSummary:
    def test_copilot_has_impact_summary_container(self):
        assert 'id="copilotImpactSummary"' in INDEX

    def test_copilot_renders_summary_for_impact(self):
        block = APP[APP.index("function renderCopilotAnswer"):APP.index("function copyCopilotAnswer")]
        assert "copilotImpactSummary" in block
        assert "impactSemanticCard(res)" in block
        assert "impactBlastCard(res)" in block


class TestStyles:
    def test_css_classes_present(self):
        for cls in (".impact-summary-card", ".isc-label", ".blast-metrics",
                    ".bm-num", ".impact-arch-summary", ".tag.sym"):
            assert cls in CSS, cls
