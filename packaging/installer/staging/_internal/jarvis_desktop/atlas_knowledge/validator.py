"""Batch validation for Atlas knowledge catalog."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema import ConceptRecord, validate_concept


def validate_catalog(concepts: Dict[str, ConceptRecord]) -> Tuple[bool, List[str]]:
    """Validate entire catalog; return (ok, error lines)."""
    errors: List[str] = []
    alias_owner: Dict[str, str] = {}
    for cid, rec in concepts.items():
        if cid != rec.concept_id:
            errors.append(f"key mismatch: {cid} vs {rec.concept_id}")
        ok, errs = validate_concept(rec)
        if not ok:
            errors.append(f"{cid}: " + "; ".join(errs))
        for alias in rec.aliases:
            key = alias.lower().strip()
            if not key:
                continue
            if key in alias_owner and alias_owner[key] != cid:
                errors.append(f"duplicate alias '{alias}': {alias_owner[key]} and {cid}")
            else:
                alias_owner[key] = cid
    return (len(errors) == 0, errors)
