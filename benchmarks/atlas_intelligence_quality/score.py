"""Score recorded Atlas benchmark observations against the checked-in contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent


def _set(values: Iterable[object]) -> set[str]:
    return {str(value) for value in values}


def _edges(values: Iterable[object]) -> set[tuple[str, str]]:
    output: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, list) and len(value) == 2:
            output.add((str(value[0]), str(value[1])))
    return output


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def score(manifest: dict, observations: dict) -> dict:
    totals = {"file_tp": 0, "file_selected": 0, "file_expected": 0, "dep_tp": 0, "dep_selected": 0, "dep_expected": 0,
              "citation_valid": 0, "citation_total": 0, "impact_fp": 0, "impact_fn": 0, "impact_expected": 0,
              "stale_pass": 0, "stale_total": 0, "isolation_pass": 0, "isolation_total": 0}
    detail: dict[str, dict] = {}
    for name, expected in manifest["scenarios"].items():
        observed = observations.get("scenarios", {}).get(name, {})
        selected = _set(observed.get("relevant_files", []))
        wanted = _set(expected.get("relevant_files", []))
        edges = _edges(observed.get("dependencies", []))
        expected_edges = _edges(expected.get("dependencies", []))
        citations = _set(observed.get("citations", []))
        files = _set(expected.get("files", []))
        impacts = _set(observed.get("impact", []))
        expected_impact = _set(expected.get("impact", []))
        totals["file_tp"] += len(selected & wanted); totals["file_selected"] += len(selected); totals["file_expected"] += len(wanted)
        totals["dep_tp"] += len(edges & expected_edges); totals["dep_selected"] += len(edges); totals["dep_expected"] += len(expected_edges)
        totals["citation_valid"] += len(citations & files); totals["citation_total"] += len(citations)
        totals["impact_fp"] += len(impacts - expected_impact); totals["impact_fn"] += len(expected_impact - impacts); totals["impact_expected"] += len(expected_impact)
        stale = bool(observed.get("stale_context_rejected")) is bool(expected.get("stale_context_rejected"))
        totals["stale_pass"] += int(stale); totals["stale_total"] += 1
        if "cross_repository_isolated" in expected:
            isolated = bool(observed.get("cross_repository_isolated")) is bool(expected["cross_repository_isolated"])
            totals["isolation_pass"] += int(isolated); totals["isolation_total"] += 1
        detail[name] = {"file_precision": _ratio(len(selected & wanted), len(selected)), "file_recall": _ratio(len(selected & wanted), len(wanted)),
                        "dependency_precision": _ratio(len(edges & expected_edges), len(edges)), "dependency_recall": _ratio(len(edges & expected_edges), len(expected_edges)),
                        "citation_validity": _ratio(len(citations & files), len(citations)), "stale_context": stale}
    return {"observation_contract_scored": True, "metrics": {
        "file_relevance_precision": _ratio(totals["file_tp"], totals["file_selected"]), "file_relevance_recall": _ratio(totals["file_tp"], totals["file_expected"]),
        "dependency_precision": _ratio(totals["dep_tp"], totals["dep_selected"]), "dependency_recall": _ratio(totals["dep_tp"], totals["dep_expected"]),
        "citation_validity": _ratio(totals["citation_valid"], totals["citation_total"]), "stale_context_detection": _ratio(totals["stale_pass"], totals["stale_total"]),
        "cross_repository_isolation": _ratio(totals["isolation_pass"], totals["isolation_total"]), "impact_false_positive_rate": _ratio(totals["impact_fp"], totals["impact_fp"] + totals["impact_expected"]),
        "impact_false_negative_rate": _ratio(totals["impact_fn"], totals["impact_expected"]),
      }, "scenarios": detail}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: py -3 score.py observations.json", file=sys.stderr)
        return 2
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    observations = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(score(manifest, observations), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
