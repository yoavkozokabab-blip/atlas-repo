"""Phase 136 — fast unit tests for the generalization benchmark framework
(scorer, registry, report). No repository scans required."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.generalization import registry, scorer, report  # noqa: E402


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
class TestRegistry:
    def test_has_eleven_plus_targets(self):
        assert len(registry.REPOS) >= 11

    def test_covers_multiple_languages(self):
        langs = {r.language for r in registry.REPOS}
        assert {"python", "typescript"} <= langs
        assert len(langs) >= 3  # python, typescript, go/rust

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATLAS_BENCH_DJANGO", str(tmp_path))
        spec = next(r for r in registry.REPOS if r.id == "django")
        assert spec.resolve_path() == tmp_path

    def test_unavailable_is_graceful(self):
        spec = registry.RepoSpec("nonexistent_xyz", "X", "python", "f", "python")
        assert spec.resolve_path() is None


# --------------------------------------------------------------------------
# Scorer — bounds + failure categorization
# --------------------------------------------------------------------------
class TestScorer:
    def test_understanding_scan_failure(self):
        r = scorer.score_understanding("x", {"ok": False})
        assert r["score"] == 0.0
        assert r["failures"][0]["category"] == scorer.GRAPH_FAILURE

    def test_understanding_full(self):
        summary = {"ok": True, "module_count": 500, "explanation": "x" * 120,
                   "subsystems": [1, 2, 3], "entry_points": ["a"], "top_risks": [1],
                   "top_hubs": [1], "architecture": {"top_boundaries": [1], "hubs_risks_identical": False}}
        r = scorer.score_understanding("x", summary)
        assert 0 <= r["score"] <= 100
        assert r["score"] >= 90

    def test_impact_fallback_is_semantic_routing_failure(self):
        results = [{"prompt": "what breaks if I remove caching", "concept": "caching",
                    "response": {"answer": "Name a file, module, or architecture concept to analyze"}}]
        r = scorer.score_impact("x", results)
        assert r["score"] == 0.0
        assert r["fallback_rate"] == 1.0
        assert r["failures"][0]["category"] == scorer.SEMANTIC_ROUTING_FAILURE

    def test_impact_resolved(self):
        results = [{"prompt": "what breaks if I remove authentication", "concept": "authentication",
                    "response": {"answer": "Removing authentication affects 5 importers",
                                 "semantic_label": "authentication", "resolved_modules": ["auth/x.py"],
                                 "direct_impact": ["a", "b"], "confidence": "high"}}]
        r = scorer.score_impact("x", results)
        assert r["score"] > 50
        assert r["fallback_rate"] == 0.0

    def test_investigation_dotfile_is_failure(self):
        results = [{"symptom": "duplicate events", "response": {"plan": {"likely_modules": [".prettierrc.js"], "hypotheses": [{}]}}}]
        r = scorer.score_investigation("x", results)
        assert any(f["category"] == scorer.INVESTIGATION_FAILURE for f in r["failures"])

    def test_investigation_clean(self):
        results = [{"symptom": "duplicate events", "response": {"plan": {"likely_modules": ["core/event.py"], "hypotheses": [{}]}}}]
        r = scorer.score_investigation("x", results)
        assert r["score"] == 100.0

    def test_build_complete(self):
        results = [{"request": "add rate limiting", "response": {"plan": {
            "likely_affected_modules": ["api.py"], "implementation_order": ["a"],
            "tests_required": ["t"], "rollback_plan": ["r"]}}}]
        r = scorer.score_build("x", results)
        assert r["score"] == 100.0

    def test_overall_weighting(self):
        assert scorer.overall(100, 100, 100, 100) == 100.0
        assert scorer.overall(0, 0, 0, 0) == 0.0
        ov = scorer.overall(80, 60, 70, 90)
        assert 60 <= ov <= 90


# --------------------------------------------------------------------------
# Report generation (synthetic record)
# --------------------------------------------------------------------------
class TestReport:
    def _rec(self):
        return {
            "id": "demo", "display": "Demo", "language": "python", "framework": "f",
            "category": "python", "available": True, "path": "/x", "status": "ok",
            "scan": {"module_count": 100, "edges": 200, "subsystem_count": 5, "files": 300,
                     "massive_mode": False, "graph_detail": "full", "scan_seconds": 1.0},
            "scores": {"understanding": 90, "impact": 50, "investigation": 80, "build": 100, "overall": 77.0},
            "understanding": {"score": 90, "components": {"graph_built": 20}},
            "impact": {"score": 50, "resolution_rate": 0.5, "fallback_rate": 0.5, "resolved": 2, "total": 4},
            "investigation": {"score": 80, "grounded_rate": 0.8, "clean_rate": 1.0, "avg_modules": 4.0},
            "build": {"score": 100, "with_modules": 4, "total": 4},
            "impact_samples": [], "investigation_samples": [], "build_samples": [],
            "failures": [{"scenario": "s", "expected": "e", "actual": "a", "root_cause": "rc",
                          "subsystem": "ss", "category": scorer.RESOLVER_FAILURE}],
        }

    def test_repo_report_renders(self):
        md = report.repo_report(self._rec())
        assert "Final Score" in md and "Failure Analysis" in md and "Demo" in md

    def test_leaderboard_sorts_and_lists_unavailable(self):
        recs = [self._rec(),
                {"id": "u", "display": "Unavail", "language": "go", "available": False,
                 "status": "unavailable", "scores": {}, "scan": {}}]
        md = report.leaderboard(recs)
        assert "Leaderboard" in md and "Unavail" in md and "Demo" in md

    def test_generalization_report(self):
        md = report.generalization_report([self._rec()])
        assert "Mean scores" in md and "Failure categories" in md and "Honest findings" in md

    def test_repo_top5_failures_format(self):
        rec = self._rec()
        rec["failures"] = [
            {"scenario": "what breaks if I remove caching", "expected": "e", "actual": "fallback",
             "root_cause": "concept absent", "subsystem": "resolver",
             "category": scorer.SEMANTIC_ROUTING_FAILURE}]
        freq = report._pattern_repo_freq([rec])
        md = report.repo_top5_failures(rec, freq)
        assert "Top 5 Failures" in md
        assert "Failure:" in md and "Frequency:" in md and "Root Cause:" in md \
            and "Suggested Future Phase:" in md
        assert "Phase 137" in md  # semantic routing -> Phase 137

    def test_roadmap_analysis_sections_and_ranking(self):
        # two repos: one strong impact, one weak (semantic fallbacks) -> impact is
        # the lowest-confidence, most-damaging capability and tops the roadmap.
        strong = self._rec(); strong["id"] = "strong"; strong["display"] = "Strong"
        strong["scores"] = {"understanding": 100, "impact": 90, "investigation": 100,
                            "build": 100, "overall": 97.0}
        strong["failures"] = []
        weak = self._rec(); weak["id"] = "weak"; weak["display"] = "Weak"
        weak["scores"] = {"understanding": 100, "impact": 20, "investigation": 100,
                          "build": 100, "overall": 76.0}
        weak["failures"] = [
            {"scenario": "what breaks if I remove caching", "expected": "e", "actual": "fallback",
             "root_cause": "rc", "subsystem": "s", "category": scorer.SEMANTIC_ROUTING_FAILURE},
            {"scenario": "what breaks if I remove the logging layer", "expected": "e",
             "actual": "fallback", "root_cause": "rc", "subsystem": "s",
             "category": scorer.SEMANTIC_ROUTING_FAILURE}]
        md = report.roadmap_analysis([strong, weak])
        for section in ["consistently well", "inconsistently", "completely breaks",
                        "Most common failure class", "Most damaging failure class",
                        "Highest confidence capability", "Lowest confidence capability",
                        "Top 10 improvements"]:
            assert section in md, section
        assert "Impact Analysis" in md  # lowest-confidence capability surfaced
        assert "| +" in md  # an estimated overall gain was rendered in the table
        # impact mean 55 -> headroom 35 -> G=0.30*35=10.5 split across 2 clusters = +5.25 each
        assert "+5.25" in md
