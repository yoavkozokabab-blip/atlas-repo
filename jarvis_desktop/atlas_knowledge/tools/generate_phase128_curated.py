#!/usr/bin/env python3
"""Export Phase 128 curated concept YAML files (150 concepts). Run from repo root."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONCEPTS_DIR = ROOT / "concepts"
sys.path.insert(0, str(ROOT.parents[1]))

from jarvis_desktop.atlas_knowledge.concept_builder import build_concept  # noqa: E402
from jarvis_desktop.atlas_knowledge.phase128_catalog import PHASE128_CATALOG  # noqa: E402


def _yaml_dump(data: dict) -> str:
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    except ImportError:
        return json.dumps(data, indent=2)


def main() -> int:
    written = 0
    stats = {"source_backed": 0, "curated_deep": 0, "curated_basic": 0}
    for raw in PHASE128_CATALOG:
        cid = raw["concept_id"]
        domain = raw["domain"]
        out_dir = CONCEPTS_DIR / domain.replace(" ", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{cid}.yaml"
        path.write_text(_yaml_dump(raw), encoding="utf-8")
        written += 1
        q = raw.get("concept_quality_score", "curated_deep")
        stats[q] = stats.get(q, 0) + 1

    manifest = {
        "phase": 128,
        "total": written,
        "stats": stats,
        "concept_ids": [c["concept_id"] for c in PHASE128_CATALOG],
    }
    (ROOT / "curated_manifest_phase128.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Wrote {written} curated YAML files under {CONCEPTS_DIR}")
    print("Quality stats:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
