"""Load concepts from atlas_knowledge/concepts and packs (independent of any repo)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import ConceptRecord, validate_concept

_KNOWLEDGE_ROOT = Path(__file__).resolve().parent
CONCEPTS_DIR = _KNOWLEDGE_ROOT / "concepts"
PACKS_DIR = _KNOWLEDGE_ROOT / "packs"
TAXONOMY_DIR = _KNOWLEDGE_ROOT / "taxonomy"
INDEXES_DIR = _KNOWLEDGE_ROOT / "indexes"
CACHE_DIR = _KNOWLEDGE_ROOT / "cache"


def knowledge_root() -> Path:
    return _KNOWLEDGE_ROOT


def load_taxonomy() -> Dict[str, Any]:
    path = TAXONOMY_DIR / "domains.json"
    if not path.is_file():
        return {"domains": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_yaml_minimal(text: str) -> Dict[str, Any]:
    """Minimal YAML subset parser (no PyYAML dependency): key: value and - lists."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    # Fallback: JSON if file is .json disguised or simple structure
    if text.strip().startswith("{"):
        return json.loads(text)
    raise ValueError("PyYAML not installed and file is not JSON")


def _record_from_file(path: Path) -> Optional[ConceptRecord]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(text)
    else:
        raw = _parse_yaml_minimal(text)
    if isinstance(raw, list):
        raise ValueError(f"expected object in {path}")
    if "concept_id" not in raw and "id" in raw:
        raw["concept_id"] = raw["id"]
    rec = ConceptRecord.from_dict(raw)
    ok, errs = validate_concept(rec, strict=False)
    if not ok:
        return None
    return rec


def load_concepts_from_disk(
    *,
    include_packs: bool = True,
    include_legacy_embedded: bool = True,
) -> Dict[str, ConceptRecord]:
    """Load all concepts; later sources do not override earlier (first wins)."""
    concepts: Dict[str, ConceptRecord] = {}

    def _add(rec: Optional[ConceptRecord]) -> None:
        # Later sources override earlier (curated YAML > packs > legacy).
        if rec:
            concepts[rec.concept_id] = rec

    if include_legacy_embedded:
        from . import legacy_embedded

        for cid, raw in legacy_embedded.LEGACY_CONCEPTS.items():
            _add(_migrate_legacy(cid, raw))

    if include_packs and PACKS_DIR.is_dir():
        for pack_path in sorted(PACKS_DIR.glob("*.json")):
            try:
                data = json.loads(pack_path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else data.get("concepts", [])
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    rec = ConceptRecord.from_dict(raw)
                    ok, _ = validate_concept(rec, strict=False)
                    if ok:
                        _add(rec)
            except (OSError, ValueError, json.JSONDecodeError):
                continue

    for path in sorted(CONCEPTS_DIR.rglob("*.yaml")):
        try:
            _add(_record_from_file(path))
        except (OSError, ValueError):
            continue
    for path in sorted(CONCEPTS_DIR.rglob("*.yml")):
        try:
            _add(_record_from_file(path))
        except (OSError, ValueError):
            continue
    for path in sorted(CONCEPTS_DIR.rglob("*.json")):
        if "packs" in path.parts:
            continue
        try:
            _add(_record_from_file(path))
        except (OSError, ValueError):
            continue

    # Cached concepts (retrieval reuse)
    if CACHE_DIR.is_dir():
        for path in CACHE_DIR.glob("*.json"):
            if path.name.startswith("."):
                continue
            try:
                _add(_record_from_file(path))
            except (OSError, ValueError):
                continue

    return concepts


def _migrate_legacy(cid: str, raw: Dict[str, Any]) -> ConceptRecord:
    """Convert Phase 125 embedded dict to ConceptRecord."""
    merged = dict(raw)
    merged["concept_id"] = cid
    merged["description"] = raw.get("meaning") or raw.get("description") or ""
    merged["category"] = raw.get("feature_type") or raw.get("category") or "feature"
    merged["risks"] = list(raw.get("implementation_risks") or raw.get("risks") or [])
    merged["failure_modes"] = list(raw.get("common_bugs") or raw.get("failure_modes") or [])
    merged["testing"] = list(raw.get("tests_to_run") or raw.get("testing") or [])
    merged["verification"] = list(raw.get("verification") or [])
    merged["requirements"] = list(raw.get("required_inputs") or []) + list(raw.get("required_outputs") or [])
    merged["common_implementations"] = list(raw.get("typical_locations") or [])
    merged["aliases"] = list(raw.get("aliases") or [])
    if cid not in merged["aliases"]:
        merged["aliases"] = [cid.replace("_", " "), *merged["aliases"]]
    if not merged.get("references"):
        merged["references"] = [f"atlas://legacy/{cid}"]
    if not merged.get("risks"):
        merged["risks"] = ["Investigation-only pattern — validate assumptions before changing code."]
    if not merged.get("failure_modes"):
        merged["failure_modes"] = list(merged.get("common_bugs") or ["Unknown failure mode — gather traces."])
    if not merged.get("testing"):
        merged["testing"] = ["Add regression test after root cause is confirmed."]
    if not merged.get("verification"):
        merged["verification"] = list(merged.get("verification") or ["Reproduce symptom with minimal fixture."])
    return ConceptRecord.from_dict(merged)


def build_alias_index(concepts: Dict[str, ConceptRecord]) -> Dict[str, str]:
    """alias (lower) -> concept_id"""
    index: Dict[str, str] = {}
    for cid, rec in concepts.items():
        for alias in rec.aliases:
            key = alias.lower().strip()
            if key and key not in index:
                index[key] = cid
        if cid not in index.values():
            index[cid.replace("_", " ")] = cid
    return index


def persist_alias_index(index: Dict[str, str]) -> None:
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    path = INDEXES_DIR / "alias_index.json"
    path.write_text(json.dumps(index, indent=0, sort_keys=True), encoding="utf-8")


def load_alias_index(concepts: Dict[str, ConceptRecord]) -> Dict[str, str]:
    path = INDEXES_DIR / "alias_index.json"
    if path.is_file():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict) and len(stored) > 100:
                return {str(k).lower(): str(v) for k, v in stored.items()}
        except (OSError, json.JSONDecodeError):
            pass
    index = build_alias_index(concepts)
    persist_alias_index(index)
    return index
