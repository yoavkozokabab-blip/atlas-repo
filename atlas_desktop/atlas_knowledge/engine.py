"""Atlas Knowledge Engine — classify, score, and resolve concepts (Phase 127)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from .loader import CACHE_DIR, load_alias_index, load_concepts_from_disk, load_taxonomy
from .retrieval import RETRIEVAL_BLOCKLIST, RetrievalPolicy
from .quality import is_shallow_generated, quality_confidence_boost, quality_rank, quality_ui_label
from .schema import ConceptRecord
from .validator import validate_catalog

# Score threshold: at or above → local knowledge only (no retrieval).
LOCAL_CONFIDENCE_THRESHOLD = 2.0
HIGH_SCORE = 5.0


@dataclass
class ConceptMatch:
    concept_id: Optional[str]
    record: Optional[ConceptRecord]
    score: float
    hits: List[str]
    source: str  # local | cache | retrieval | none
    concept_confidence: str  # high | medium | low
    unknowns: List[str] = field(default_factory=list)


@dataclass
class ConceptClassification:
    """Backward-compatible with domain_knowledge.Classification."""
    concept_id: Optional[str]
    concept_name: str
    concept_title: str
    domain: str
    domain_label: str
    feature_type: str
    concept_confidence: str
    repo_mapping_confidence: str
    unknowns: List[str] = field(default_factory=list)
    architecture_pattern: str = ""
    match: Optional[ConceptMatch] = None
    record: Optional[ConceptRecord] = None


@dataclass
class RepoFileRoles:
    must_inspect: List[str]
    likely_modify: List[str]
    verify_only: List[str]
    do_not_touch: List[str]
    dedicated_module_found: bool
    integration_note: str


class KnowledgeEngine:
    """Singleton-style engine; works without any repository loaded."""

    def __init__(self) -> None:
        self._concepts: Optional[Dict[str, ConceptRecord]] = None
        self._alias_index: Optional[Dict[str, str]] = None
        self._taxonomy: Optional[Dict[str, Any]] = None
        self._retrieval = RetrievalPolicy(CACHE_DIR, enabled=False)
        self._validation_errors: List[str] = []

    def reload(self) -> int:
        self._concepts = load_concepts_from_disk()
        ok, errs = validate_catalog(self._concepts)
        self._validation_errors = errs if not ok else []
        self._alias_index = load_alias_index(self._concepts)
        self._taxonomy = load_taxonomy()
        return len(self._concepts)

    @property
    def concepts(self) -> Dict[str, ConceptRecord]:
        if self._concepts is None:
            self.reload()
        assert self._concepts is not None
        return self._concepts

    @property
    def concept_count(self) -> int:
        return len(self.concepts)

    def domain_label(self, domain: str) -> str:
        tax = self._taxonomy or load_taxonomy()
        domains = tax.get("domains") or {}
        entry = domains.get(domain) or {}
        return entry.get("label") or domain.replace("_", " ").title()

    def get(self, concept_id: str) -> Optional[ConceptRecord]:
        return self.concepts.get(concept_id)

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower().strip())

    def _alias_score(self, text: str, aliases: List[str]) -> Tuple[float, List[str]]:
        norm = self._normalize(text)
        hits: List[str] = []
        score = 0.0
        for alias in sorted(aliases, key=len, reverse=True):
            a = alias.lower().strip()
            if not a:
                continue
            if len(a) <= 4:
                if re.search(rf"\b{re.escape(a)}\b", norm):
                    hits.append(a)
                    score += 2.0 + min(len(a) / 10.0, 3.0)
            elif a in norm:
                hits.append(a)
                score += 2.0 + min(len(a) / 10.0, 3.0)
            elif len(a) > 4 and re.search(rf"\b{re.escape(a)}\b", norm):
                hits.append(a)
                score += 1.5 + min(len(a) / 12.0, 2.0)
        return score, hits

    def match_text(self, text: str, *, mode: str = "build") -> ConceptMatch:
        norm = self._normalize(text)
        if not norm:
            return ConceptMatch(None, None, 0.0, [], "none", "low", ["Empty request"])

        best_id: Optional[str] = None
        best_score = 0.0
        best_hits: List[str] = []

        best_rank = -1
        for cid, rec in self.concepts.items():
            if mode == "build" and rec.investigate_only:
                continue
            score, hits = self._alias_score(norm, rec.aliases)
            score += quality_confidence_boost(rec.concept_quality_score)
            rank = quality_rank(rec.concept_quality_score)
            if score > best_score or (score == best_score and rank > best_rank):
                best_score = score
                best_id = cid
                best_hits = hits
                best_rank = rank

        # P164 — quality boost alone must not pass threshold; require real hits.
        if best_id and best_score >= LOCAL_CONFIDENCE_THRESHOLD and len(best_hits) >= 1:
            rec = self.concepts[best_id]
            q = rec.computed_quality_score
            if q in ("source_backed", "curated_deep") and (best_score >= HIGH_SCORE or len(best_hits) >= 2):
                conf = "high"
            elif q == "generated_template":
                conf = "low" if mode == "investigate" else "medium"
            else:
                conf = "medium"
            return ConceptMatch(best_id, rec, best_score, best_hits, "local", conf)

        # Try cache (only when at least one alias/text hit grounded the concept)
        if best_id and len(best_hits) >= 1:
            cached = self._retrieval.load_cached(best_id)
            if cached:
                return ConceptMatch(cached.concept_id, cached, best_score, best_hits, "cache", "medium")

        # Retrieval policy (stub — disabled by default)
        if self._retrieval.should_retrieve(
            text, local_score=best_score, matched_id=best_id, threshold=LOCAL_CONFIDENCE_THRESHOLD
        ):
            retrieved = self._retrieval.attempt_retrieval(text)
            if retrieved:
                return ConceptMatch(
                    retrieved.concept_id, retrieved, best_score, best_hits, "retrieval", "low"
                )

        # Partial score from quality boost alone is not a concept match.
        if best_id and best_score > 0 and len(best_hits) >= 1:
            rec = self.concepts[best_id]
            return ConceptMatch(best_id, rec, best_score, best_hits, "local", "low")

        unknowns = ["No domain concept matched — plan relies on path keywords only."]
        if best_id and best_score > 0 and not best_hits:
            unknowns.append(
                "Quality-tier boost alone is insufficient — add explicit concept terms or file paths."
            )
        return ConceptMatch(None, None, best_score, best_hits, "none", "low", unknowns)

    def classify_request(self, text: str, *, mode: str = "build") -> ConceptClassification:
        m = self.match_text(text, mode=mode)
        if not m.record:
            unknowns = list(m.unknowns)
            if mode == "investigate":
                unknowns.append("Add subsystem, file path, or concept name for sharper routing.")
            return ConceptClassification(
                concept_id=None,
                concept_name="",
                concept_title="",
                domain="",
                domain_label="",
                feature_type="general",
                concept_confidence="low",
                repo_mapping_confidence="low",
                unknowns=unknowns,
                match=m,
            )

        rec = m.record
        domain = rec.domain
        pattern = rec.feature_type or rec.category
        architecture_pattern = self._architecture_pattern(rec)

        unknowns = list(m.unknowns)
        if m.concept_confidence != "high":
            unknowns.append("Concept match is partial — confirm the request targets this concept.")
        if rec.investigate_only:
            unknowns.append("This pattern is optimized for investigation, not greenfield implementation.")
        if m.source == "retrieval":
            unknowns.append("Knowledge from retrieval stub — validate against official documentation.")
        if rec and is_shallow_generated(rec.concept_quality_score):
            if mode == "investigate":
                unknowns.append(
                    "Matched knowledge is template-generated only — treat hypotheses as leads; "
                    "prefer curated/source-backed concepts or add file paths."
                )
            else:
                unknowns.append(
                    "Knowledge depth is generated-template — verify against official docs before implementing."
                )

        return ConceptClassification(
            concept_id=m.concept_id,
            concept_name=rec.name,
            concept_title=rec.title or rec.name,
            domain=domain,
            domain_label=self.domain_label(domain),
            feature_type=pattern,
            concept_confidence=m.concept_confidence,
            repo_mapping_confidence="low",
            unknowns=unknowns,
            architecture_pattern=architecture_pattern,
            match=m,
            record=rec,
        )

    def _architecture_pattern(self, rec: ConceptRecord) -> str:
        locs = rec.common_implementations or rec.typical_locations
        if rec.domain == "trading" and rec.category == "indicator":
            return "price-series indicator → strategy signal → backtest/live paths"
        if rec.domain == "security" and rec.category in {"auth", "authentication"}:
            return "identity → session/token → middleware → protected routes"
        if locs:
            return " → ".join(locs[:4])
        return "subsystem-specific"

    def search_terms(self, classification: ConceptClassification) -> Set[str]:
        if not classification.record:
            return set()
        rec = classification.record
        terms: Set[str] = set()
        for kw in rec.path_keywords:
            terms.add(kw.lower())
        for alias in rec.aliases[:5]:
            for tok in re.findall(r"[a-z][a-z0-9_]{2,}", alias.lower()):
                terms.add(tok)
        return terms

    def map_to_repository(
        self,
        classification: ConceptClassification,
        modules: List[Dict[str, Any]],
        risks_map: Dict[str, Dict[str, Any]],
        *,
        scored_paths: Optional[List[str]] = None,
    ) -> RepoFileRoles:
        if not classification.record:
            return RepoFileRoles(
                must_inspect=list(scored_paths or [])[:5],
                likely_modify=[],
                verify_only=[],
                do_not_touch=[],
                dedicated_module_found=False,
                integration_note="No scanned modules available for concept mapping.",
            )

        rec = classification.record
        allowed = {n.get("path") for n in modules if n.get("path")}
        keywords = tuple(k.lower() for k in rec.path_keywords)
        verify_kw = ("backtest", "paper", "live", "sim", "config", "settings", "test")
        modify_kw = list(keywords)[:8] or ["service", "api", "core"]

        ranked: List[Tuple[float, str]] = []
        for node in modules:
            path = node.get("path") or ""
            if path not in allowed:
                continue
            p = path.lower().replace("\\", "/")
            score = 0.0
            for kw in keywords:
                if kw and kw in p:
                    score += 3.0
            if scored_paths and path in scored_paths[:15]:
                score += 2.0
            risk = risks_map.get(path) or {}
            score += min(2.0, float(risk.get("total_score", 0) or 0) / 30.0)
            if score > 0:
                ranked.append((score, path))
        ranked.sort(key=lambda x: (-x[0], x[1]))

        paths = [p for _, p in ranked]
        dedicated = bool(paths) and any(
            kw in paths[0].lower() for kw in keywords if len(kw) > 3
        )

        must = paths[:5]
        likely_modify = [p for p in paths if any(k in p.lower() for k in modify_kw)][:6]
        verify_only = [p for p in paths if any(k in p.lower() for k in verify_kw)][:6]
        if not likely_modify and must:
            likely_modify = must[:3]

        do_not_touch = []
        for p in paths:
            row = risks_map.get(p) or {}
            if int(row.get("fan_in", 0) or 0) >= 20 and p not in must:
                do_not_touch.append(p)

        if dedicated:
            note = f"Dedicated modules found for {rec.name}."
        elif must:
            note = (
                f"No dedicated {rec.name.lower()} module found. "
                f"Candidate integration points: {', '.join(must[:4])}."
            )
        else:
            note = (
                f"No production module matched {rec.name} keywords. "
                "Inspect entry points and top import hubs in Repository Map."
            )

        mapping_conf = "high" if dedicated and len(must) >= 2 else ("medium" if must else "low")
        classification.repo_mapping_confidence = mapping_conf

        return RepoFileRoles(
            must_inspect=must,
            likely_modify=likely_modify,
            verify_only=verify_only,
            do_not_touch=do_not_touch[:5],
            dedicated_module_found=dedicated,
            integration_note=note,
        )

    def knowledge_block(self, classification: ConceptClassification) -> Dict[str, Any]:
        """Structured block for UI and prompts."""
        if not classification.record:
            return {"applied": False, "source": "none"}
        rec = classification.record
        m = classification.match
        quality = rec.computed_quality_score
        return {
            "applied": True,
            "source": m.source if m else "local",
            "concept_quality_score": quality,
            "knowledge_quality_label": quality_ui_label(quality),
            "knowledge_depth_warning": is_shallow_generated(quality),
            "concept_id": rec.concept_id,
            "concept_name": rec.name,
            "concept_title": rec.title or rec.name,
            "domain": rec.domain,
            "domain_label": classification.domain_label,
            "category": rec.category,
            "feature_type": classification.feature_type,
            "concept_confidence": classification.concept_confidence,
            "repo_mapping_confidence": classification.repo_mapping_confidence,
            "meaning": rec.description,
            "concept_understanding": rec.description,
            "when_to_use": rec.when_to_use,
            "requirements": rec.requirements,
            "implementation_strategies": rec.implementation_strategies,
            "common_implementations": rec.common_implementations,
            "risks": rec.risks,
            "knowledge_risks": rec.risks,
            "failure_modes": rec.failure_modes,
            "domain_failure_modes": rec.failure_modes,
            "verification": rec.verification,
            "testing": rec.testing,
            "related_concepts": rec.related_concepts,
            "references": rec.references,
            "why_this_matters": self._why_matters(rec),
            "architecture_pattern": classification.architecture_pattern,
            "unknowns": classification.unknowns,
            "catalog_confidence": rec.confidence,
            "security_risks": rec.security_risks,
            "performance_risks": rec.performance_risks,
        }

    def _why_matters(self, rec: ConceptRecord) -> str:
        if rec.domain == "trading" and rec.category == "indicator":
            return (
                f"{rec.name} is a price-series indicator — compute consistently across "
                "backtest and live/paper with correct warmup and no lookahead."
            )
        if rec.domain == "security":
            return f"{rec.name} affects trust boundaries — validate tokens, expiration, and replay protection."
        if rec.domain == "databases":
            return f"{rec.name} affects data integrity and query performance at scale."
        return f"Changes involving {rec.name} touch {', '.join((rec.common_implementations or ['core subsystems'])[:3])}."

    def enrich_build_plan(
        self,
        plan: Dict[str, Any],
        classification: ConceptClassification,
        roles: RepoFileRoles,
    ) -> None:
        if not classification.record:
            plan["domain_knowledge"] = {"applied": False}
            plan["knowledge_engine"] = {"applied": False}
            return

        rec = classification.record
        block = self.knowledge_block(classification)
        block["file_roles"] = {
            "must_inspect": roles.must_inspect,
            "likely_modify": roles.likely_modify,
            "verify_only": roles.verify_only,
            "do_not_touch": roles.do_not_touch,
        }
        block["integration_note"] = roles.integration_note
        block["dedicated_module_found"] = roles.dedicated_module_found

        if roles.must_inspect:
            plan["files_to_inspect_first"] = roles.must_inspect[:8]
        if roles.likely_modify:
            plan["files_likely_to_change"] = roles.likely_modify[:8]
            plan["likely_affected_modules"] = list(
                dict.fromkeys(roles.likely_modify + (plan.get("likely_affected_modules") or []))
            )[:12]

        arch = list(plan.get("architectural_risks") or [])
        for r in rec.risks:
            label = f"[knowledge] {r}"
            if label not in arch:
                arch.append(label)
        plan["architectural_risks"] = arch[:16]

        vplan = list(plan.get("verification_plan") or [])
        for v in rec.verification:
            if v not in vplan:
                vplan.append(v)
        plan["verification_plan"] = vplan[:14]

        tests = list(plan.get("tests_likely_affected") or [])
        for t in rec.testing:
            if t not in tests:
                tests.append(t)
        plan["tests_likely_affected"] = tests
        plan["tests_required"] = tests

        steps = rec.implementation_steps
        if steps:
            plan["domain_implementation_steps"] = steps
            if not plan.get("implementation_order"):
                plan["implementation_order"] = [f"Step: {s}" for s in steps[:8]]

        plan["implementation_strategy"] = steps[:8] if steps else rec.common_implementations[:6]
        plan["domain_knowledge"] = block
        plan["knowledge_engine"] = block
        plan["domain_prompt_section"] = self.format_domain_prompt_section(classification)
        roles_block = block.get("file_roles") or {}
        if roles_block:
            plan["domain_prompt_section"] += (
                "\n### Repository roles\n"
                f"- Must inspect: {', '.join(roles_block.get('must_inspect') or []) or 'n/a'}\n"
                f"- Likely modify: {', '.join(roles_block.get('likely_modify') or []) or 'n/a'}\n"
            )

    def enrich_investigation_plan(
        self,
        plan: Dict[str, Any],
        classification: ConceptClassification,
        roles: RepoFileRoles,
    ) -> None:
        if not classification.record:
            plan["domain_knowledge"] = {"applied": False}
            return

        rec = classification.record
        block = self.knowledge_block(classification)
        block["file_roles"] = {
            "must_inspect": roles.must_inspect,
            "likely_modify": roles.likely_modify,
            "verify_only": roles.verify_only,
        }
        block["integration_note"] = roles.integration_note

        checklist = list(plan.get("verification_checklist") or [])
        for item in rec.failure_modes + rec.verification[:4]:
            if item not in checklist:
                checklist.append(item)
        plan["verification_checklist"] = checklist[:14]

        if roles.must_inspect:
            plan["inspect_first"] = roles.must_inspect[:5]
            plan["suggested_files_to_inspect"] = roles.must_inspect[:8]
            plan["likely_modules"] = list(
                dict.fromkeys(roles.must_inspect + (plan.get("likely_modules") or []))
            )[:10]

        if rec.failure_modes:
            plan["logical_hypothesis"] = rec.failure_modes[0]
            plan["domain_failure_modes"] = rec.failure_modes[:8]
            plan["known_failure_modes"] = rec.failure_modes[:8]

        plan["domain_knowledge"] = block
        plan["knowledge_engine"] = block
        plan["domain_prompt_section"] = self.format_domain_prompt_section(classification)

    def format_domain_prompt_section(self, classification: ConceptClassification) -> str:
        """DOMAIN KNOWLEDGE block for Claude/Cursor/Codex exports."""
        if not classification.record:
            return ""
        rec = classification.record
        qlabel = quality_ui_label(rec.concept_quality_score)
        lines = [
            "## DOMAIN KNOWLEDGE",
            f"**Concept:** {rec.name} ({rec.title or rec.name})",
            f"**Domain:** {classification.domain_label} / {rec.category}",
            f"**Knowledge quality:** {qlabel} ({rec.concept_quality_score})",
            f"**Source:** {classification.match.source if classification.match else 'local'}",
            "",
            "### Meaning",
            rec.description,
            "",
        ]
        if rec.when_to_use:
            lines.extend(["### When to use", rec.when_to_use, ""])
        lines.extend([
            "### Requirements",
            *([f"- {x}" for x in rec.requirements] or ["- (see description)"]),
            "",
            "### Implementation strategies",
            *([f"- {x}" for x in rec.implementation_strategies] or ["- See requirements and repository map"]),
            "",
            "### Risks",
            *[f"- {x}" for x in rec.risks],
            "",
        ])
        if rec.security_risks:
            lines.extend(["### Security risks", *[f"- {x}" for x in rec.security_risks], ""])
        if rec.performance_risks:
            lines.extend(["### Performance risks", *[f"- {x}" for x in rec.performance_risks], ""])
        lines.extend([
            "### Failure modes",
            *[f"- {x}" for x in rec.failure_modes],
            "",
            "### Verification",
            *[f"- {x}" for x in rec.verification],
            "",
            "### Testing",
            *[f"- {x}" for x in rec.testing],
            "",
        ])
        if rec.references:
            lines.extend(["### References", *[f"- {x}" for x in rec.references], ""])
        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_engine() -> KnowledgeEngine:
    engine = KnowledgeEngine()
    engine.reload()
    return engine
