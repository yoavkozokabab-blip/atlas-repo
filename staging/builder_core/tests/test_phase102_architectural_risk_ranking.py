"""Phase 102 — architectural risk ranking engine regressions."""

from __future__ import annotations

from pathlib import Path

from builder_core import architectural_risk, ask, indexer
from builder_core.bug_intelligence import depgraph

EXACT_QUERY = (
    "Rank the top architectural risk modules in this repository using dependency "
    "graph fan-in, module size, import cycles, and test coverage."
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", '"""hub."""\n\n\ndef helper():\n    return 1\n')
    for name in ("a", "b", "c"):
        _write(
            root / f"{name}.py",
            f"from core.util import helper\n\n\ndef run_{name}():\n    return helper()\n",
        )
    _write(root / "ring" / "x.py", "from ring.y import gy\n\n\ndef gx():\n    return gy()\n")
    _write(root / "ring" / "y.py", "from ring.x import gx\n\n\ndef gy():\n    return 1\n")
    _write(root / "tests" / "test_core.py", "from core.util import helper\n\n\ndef test_helper():\n    assert helper()\n")
    for i in range(4):
        _write(root / "data" / "corpus" / f"vendor_{i}.py", f"def f_{i}():\n    return {i}\n")
    return root


def test_rank_modules_returns_structured_breakdown(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)

    assert ranking["schema_version"] == architectural_risk.SCHEMA_VERSION
    assert ranking["engine_version"] == architectural_risk.ENGINE_VERSION
    assert ranking["graph_scope"] == "production"
    assert not ranking["degraded"]
    assert ranking["ranked_modules"]

    top = ranking["ranked_modules"][0]
    assert top["rank"] == 1
    assert "score_breakdown" in top
    bd = top["score_breakdown"]
    for key in (
        "fan_in",
        "fan_out",
        "import_cycle_member",
        "module_size_loc",
        "untested_module",
        "test_evidence",
        "contract_evidence",
        "static_findings",
    ):
        assert key in bd
    assert "component_root" not in bd
    assert top["metrics"]["fan_in"] >= 1


def test_exact_query_returns_ranked_list_with_score_breakdowns(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    result = ask.answer(index, EXACT_QUERY)

    assert result["mode"] == "bottleneck"
    assert "architectural_risk_ranking" in result
    ranking = result["architectural_risk_ranking"]
    assert ranking["ranked_modules"]
    assert ranking["ranked_modules"][0]["score_breakdown"]["fan_in"] > 0

    answer = result["answer"].lower()
    assert "based on the indexed project" not in answer
    assert "degraded" not in answer
    assert "score breakdown" in answer or "total=" in result["answer"]
    assert "fan-in=" in " ".join(result["evidence"]).lower() or "fan_in" in str(
        ranking["ranked_modules"][0]["score_breakdown"]
    )


def test_hub_ranks_above_importers(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=10)
    by_label = {item["label"]: item for item in ranking["ranked_modules"]}
    hub = next((row for label, row in by_label.items() if "core" in label and "util" in label), None)
    assert hub is not None
    assert hub["metrics"]["fan_in"] >= 3
    importer_scores = [
        by_label[label]["total_score"]
        for label in by_label
        if label in ("a", "b", "c")
    ]
    assert importer_scores
    assert hub["total_score"] > max(importer_scores)


def test_cycle_modules_receive_cycle_breakdown(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=20)
    cycle_rows = [
        item for item in ranking["ranked_modules"]
        if item["score_breakdown"]["import_cycle_member"] > 0
    ]
    assert cycle_rows
    assert any("ring" in item["label"] for item in cycle_rows)


def test_data_corpus_excluded_from_ranking(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=50)
    labels = " ".join(item["label"] for item in ranking["ranked_modules"]).lower()
    assert "vendor_" not in labels


def test_impact_question_unchanged(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    result = ask.answer(
        index,
        "What breaks if I change core/util.py?",
    )
    assert result["mode"] == "impact"


def test_dependency_centrality_unchanged(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    result = ask.answer(
        index,
        "Which modules have the highest incoming-dependency count?",
    )
    assert result["mode"] == "dependency"


def test_retrieval_fallback_unchanged_for_unrelated_question(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    result = ask.answer(index, "Where is the README documentation for deployment?")
    assert result["mode"] == "retrieval"


def test_ranking_is_deterministic(tmp_path):
    root = _repo(tmp_path)
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    first = architectural_risk.rank_modules(index, graph, top=8)
    second = architectural_risk.rank_modules(index, graph, top=8)
    assert first == second
