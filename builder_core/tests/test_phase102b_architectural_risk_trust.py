"""Phase 102B — architectural risk ranking trust hardening."""

from __future__ import annotations

from pathlib import Path

from builder_core import architectural_risk, indexer
from builder_core.bug_intelligence import depgraph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_import_fan_in_dedupes_duplicate_edges(tmp_path):
    root = tmp_path / "repo"
    _write(root / "hub.py", "def h():\n    return 1\n")
    # duplicate imports in one file should count once
    _write(
        root / "a.py",
        "import hub\nfrom hub import h\nfrom hub import h as h2\n\ndef run():\n    return h() + h2()\n",
    )
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)
    hub = next(r for r in ranking["ranked_modules"] if r["label"] == "hub")
    assert hub["metrics"]["fan_in"] == 1
    assert ranking["deduped_import_pairs"] == 1


def test_cycles_are_canonical_and_deduped(tmp_path):
    root = tmp_path / "repo"
    _write(root / "p.py", "from q import gq\n\ndef gp():\n    return gq()\n")
    _write(root / "q.py", "from p import gp\n\ndef gq():\n    return 1\n")
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=10)
    canonical = ranking.get("import_cycles_canonical") or []
    assert len(canonical) == 1
    assert len(canonical[0]) == 2


def test_substring_test_name_is_not_test_evidence(tmp_path):
    root = tmp_path / "repo"
    _write(root / "isolated_big.py", "\n".join(["x = 1"] * 600))
    _write(
        root / "tests" / "test_misc.py",
        'def test_documentation_mentions_isolated_big():\n    """isolated_big is only in this string."""\n    assert True\n',
    )
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)
    row = next(r for r in ranking["ranked_modules"] if "isolated_big" in r["path"])
    assert not row["metrics"]["has_test_reference"]
    assert row["score_breakdown"]["untested_module"] > 0
    assert row["score_breakdown"]["test_evidence"] == 0.0


def test_real_test_import_counts_as_test_evidence(tmp_path):
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(
        root / "tests" / "test_core.py",
        "from core.util import helper\n\n\ndef test_helper():\n    assert helper() == 1\n",
    )
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)
    row = next(r for r in ranking["ranked_modules"] if "util" in r["path"])
    assert row["metrics"]["has_test_reference"]
    assert row["score_breakdown"]["test_evidence"] < 0
    assert row["score_breakdown"]["untested_module"] == 0.0


def test_static_and_contract_scores_are_separate(tmp_path):
    root = tmp_path / "repo"
    _write(
        root / "shapes.py",
        "def flip(x):\n    if x:\n        return 1\n    return 'no'\n",
    )
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)
    row = ranking["ranked_modules"][0]
    bd = row["score_breakdown"]
    assert "static_findings" in bd
    assert "contract_evidence" in bd
    assert bd["contract_evidence"] > 0 or bd["static_findings"] > 0
    assert "component_root" not in bd


def test_isolated_large_file_does_not_outrank_hub(tmp_path):
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    for name in ("a", "b", "c"):
        _write(
            root / f"{name}.py",
            f"from core.util import helper\n\n\ndef run_{name}():\n    return helper()\n",
        )
    _write(root / "isolated_big.py", "\n".join(["def big():\n    pass"] * 700))
    _write(
        root / "tests" / "test_big.py",
        "from isolated_big import big\n\n\ndef test_big():\n    big()\n",
    )
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=10)
    hub = next(r for r in ranking["ranked_modules"] if "util" in r["path"])
    big = next(r for r in ranking["ranked_modules"] if "isolated_big" in r["path"])
    assert big["score_breakdown"]["module_size_loc"] == 0.0
    assert not big["metrics"]["loc_risk_eligible"]
    assert hub["total_score"] > big["total_score"]


def test_rank_diagnostics_explain_scoring(tmp_path):
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(root / "a.py", "from core.util import helper\n\ndef run():\n    return helper()\n")
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=5)
    top = ranking["ranked_modules"][0]
    assert top.get("rank_diagnostics")
    assert any("fan-in" in line for line in top["rank_diagnostics"])


def test_engine_version_and_schema(tmp_path):
    root = tmp_path / "repo"
    _write(root / "m.py", "def f():\n    return 0\n")
    index = indexer.build_index(str(root))
    graph = depgraph.build_graph(str(root))
    ranking = architectural_risk.rank_modules(index, graph, top=3)
    assert ranking["schema_version"] == 2
    assert ranking["engine_version"] == "phase102b-v1"
