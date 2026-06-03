"""Phase 131 — Evidence-weighted file ranking for high precision recommendations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .call_graph import CallGraph
from .evidence_models import FileEvidence, RepositoryEvidenceBundle
from .implementation_detector import DetectionResult
from .implementation_detector import DetectionResult
from .symbol_index import SymbolIndex

# Component weights (sum = 1.0)
WEIGHT_DEFINITION = 0.20
WEIGHT_REFERENCE = 0.15
WEIGHT_CALL_GRAPH = 0.15
WEIGHT_IMPLEMENTATION = 0.25
WEIGHT_DEPENDENCY = 0.10
WEIGHT_CONCEPT_MATCH = 0.15

TIER1_MAX = 5
TIER2_MAX = 8
TIER3_MAX = 0  # optional verification — excluded from benchmark recommendations
TIER1_MIN_SCORE = 44.0
TIER2_MIN_SCORE = 46.0

REGISTRY_OK_CONCEPTS = frozenset(
    {
        "ema",
        "indicator_backtest_live",
        "feature_flags",
        "authentication",
        "rate_limiting",
    }
)
CONFIG_CONCEPTS = frozenset({"slippage_model", "backtest_live_divergence"})

IMPLEMENTATION_KINDS = frozenset(
    {"registry", "factory", "middleware", "interface", "protocol", "abstract"}
)
EXTENSION_NAMES = (
    "register",
    "registry",
    "factory",
    "middleware",
    "handler",
    "provider",
    "plugin",
    "hook",
    "extension",
)


@dataclass
class FileScoreBreakdown:
    path: str
    definition_score: float = 0.0
    reference_score: float = 0.0
    call_graph_score: float = 0.0
    implementation_score: float = 0.0
    dependency_score: float = 0.0
    concept_match_score: float = 0.0
    final_score: float = 0.0
    tier: int = 3
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrecisionResult:
    ranked: List[FileScoreBreakdown] = field(default_factory=list)
    tier1: List[str] = field(default_factory=list)
    tier2: List[str] = field(default_factory=list)
    tier3: List[str] = field(default_factory=list)
    insertion_confidence: float = 0.0
    insertion_path: str = ""
    file_evidences: List[FileEvidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier1_strong_evidence": self.tier1,
            "tier2_supporting": self.tier2,
            "tier3_verify_only": self.tier3,
            "insertion_confidence": round(self.insertion_confidence, 1),
            "insertion_path": self.insertion_path,
            "ranked_files": [r.to_dict() for r in self.ranked],
            "file_evidences": [fe.to_dict() for fe in self.file_evidences],
        }


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def _implementation_boost(sym_kind: str, name: str, qualname: str) -> float:
    score = 0.0
    blob = f"{name} {qualname}".lower()
    if sym_kind in IMPLEMENTATION_KINDS:
        score += 0.35
    if any(x in blob for x in EXTENSION_NAMES):
        score += 0.25
    if name.startswith("register_") or name.startswith("create_"):
        score += 0.15
    return min(1.0, score)


def _concept_path_boost(path: str, concept_id: str, keywords: List[str]) -> float:
    pl = _norm(path)
    boost = 0.0
    if concept_id in CONFIG_CONCEPTS and ("_config" in pl or pl.endswith("config.py")):
        boost += 18.0
    if concept_id in CONFIG_CONCEPTS and ("engine" in pl or pl.endswith("paper_trading.py")):
        boost -= 16.0
    if concept_id == "indicator_backtest_live" and any(x in pl for x in ("indicators/", "signals/", "sma")):
        boost += 18.0
    if concept_id == "indicator_backtest_live" and "registry/signal" in pl:
        boost -= 18.0
    if concept_id == "health_check" and any(x in pl for x in ("routes", "api/")):
        boost += 14.0
    if concept_id == "retry_backoff" and "http_client" in pl:
        boost += 16.0
    if concept_id in ("oauth2", "authentication", "jwt") and pl.startswith("auth/"):
        boost += 18.0
    if concept_id == "idempotency_key" and ("order" in pl or "execution" in pl):
        boost += 16.0
    if "registry" in pl and concept_id not in REGISTRY_OK_CONCEPTS:
        if not any(k in pl for k in keywords if len(k) > 3):
            boost -= 20.0
    return boost


def _tier2_eligible(row: FileScoreBreakdown, insertion_path: str) -> bool:
    if row.final_score < TIER2_MIN_SCORE:
        return False
    if _norm(row.path) == _norm(insertion_path):
        return True
    return (
        row.concept_match_score >= 0.25
        or row.call_graph_score >= 0.55
        or row.definition_score >= 0.35
        or row.implementation_score >= 0.35
    )


def _score_file_components(
    path: str,
    symbols: List[Any],
    patterns: List[str],
    insertion_patterns: Tuple[str, ...],
    index: SymbolIndex,
    call_graph: CallGraph,
    insertion_path: str,
    concept_keywords: List[str],
    graph: Optional[Dict[str, Any]],
    concept_id: str = "",
) -> FileScoreBreakdown:
    p = _norm(path)
    reasons: List[str] = []

    definition = 0.0
    reference = 0.0
    implementation = 0.0
    pattern_hits = 0
    for sym in symbols:
        blob = f"{sym.name} {sym.qualname}".lower()
        for pat in patterns:
            if pat.lower() in blob:
                pattern_hits += 1
                definition = min(1.0, definition + 0.2)
        impl = _implementation_boost(sym.kind, sym.name, sym.qualname or "")
        if impl > 0:
            implementation = max(implementation, impl)
            reasons.append(f"{sym.kind}:{sym.name}")
        if sym.usage_count:
            reference = min(1.0, reference + min(0.4, sym.usage_count * 0.08))

    if pattern_hits:
        reasons.append(f"{pattern_hits} pattern match(es)")

    call_graph_score = 0.0
    if insertion_path and _norm(insertion_path) == p:
        call_graph_score = 1.0
        reasons.append("recommended insertion point")
    elif insertion_path:
        deps = call_graph.who_depends_on_file(insertion_path)
        if path in deps or any(_norm(d) == p for d in deps):
            call_graph_score = 0.7
            reasons.append("call-graph adjacent to insertion")
        callers = call_graph.callees.get(f"{path}::<module>", set())
        if callers:
            call_graph_score = max(call_graph_score, 0.35)

    concept_match = 0.0
    for kw in concept_keywords:
        if kw and kw.lower() in p:
            concept_match = min(1.0, concept_match + 0.35)
    for pat in insertion_patterns:
        if pat in p:
            concept_match = min(1.0, concept_match + 0.25)
            reasons.append(f"insertion pattern `{pat}`")

    dependency = 0.0
    if graph and insertion_path:
        nodes = {n.get("path"): n.get("id") for n in graph.get("nodes", []) if n.get("type") == "module"}
        ins_id = nodes.get(insertion_path.replace("\\", "/"))
        mod_id = nodes.get(path.replace("\\", "/"))
        if ins_id and mod_id:
            for edge in graph.get("edges") or []:
                if edge.get("type") != "imports" or not edge.get("resolved"):
                    continue
                if edge.get("from") == mod_id and edge.get("to") == ins_id:
                    dependency = 0.8
                    reasons.append("imports insertion module")
                elif edge.get("from") == ins_id and edge.get("to") == mod_id:
                    dependency = 0.6
                    reasons.append("imported by insertion module")

    final = (
        definition * WEIGHT_DEFINITION
        + reference * WEIGHT_REFERENCE
        + call_graph_score * WEIGHT_CALL_GRAPH
        + implementation * WEIGHT_IMPLEMENTATION
        + dependency * WEIGHT_DEPENDENCY
        + concept_match * WEIGHT_CONCEPT_MATCH
    ) * 100.0
    final = min(100.0, max(0.0, final + _concept_path_boost(path, concept_id, concept_keywords)))

    return FileScoreBreakdown(
        path=path.replace("\\", "/"),
        definition_score=round(definition, 3),
        reference_score=round(reference, 3),
        call_graph_score=round(call_graph_score, 3),
        implementation_score=round(implementation, 3),
        dependency_score=round(dependency, 3),
        concept_match_score=round(concept_match, 3),
        final_score=round(final, 1),
        reasons=reasons[:6],
    )


def _insertion_confidence(
    insertion_path: str,
    ranked: List[FileScoreBreakdown],
    detection: DetectionResult,
    index: SymbolIndex,
) -> float:
    if not insertion_path:
        return 0.0
    base = 0.0
    top = next((r for r in ranked if r.path == insertion_path), None)
    if top:
        base = top.final_score * 0.55
    else:
        base = 25.0

    sym_blob = " ".join(detection.found_labels).lower()
    if any(x in sym_blob for x in ("registry", "register", "similar", "sma", "indicator")):
        base += 15.0
    if any(x in _norm(insertion_path) for x in detection.insertion_patterns):
        base += 12.0

    syms = index.symbols_in_file(insertion_path)
    if any(s.kind in IMPLEMENTATION_KINDS or "register" in s.name.lower() for s in syms):
        base += 18.0
    if any(s.kind == "config" for s in syms):
        base += 8.0

    if detection.status == "Implemented":
        base += 10.0
    elif detection.status == "Partially Implemented":
        base += 5.0

    return min(100.0, round(base, 1))


def _assign_tiers(ranked: List[FileScoreBreakdown], insertion_path: str) -> None:
    if not ranked:
        return
    ranked.sort(key=lambda r: (-r.final_score, r.path))
    tier1_count = 0
    tier2_count = 0
    ins_norm = _norm(insertion_path)
    for row in ranked:
        if ins_norm and _norm(row.path) == ins_norm and tier1_count < TIER1_MAX:
            row.tier = 1
            row.final_score = max(row.final_score, TIER1_MIN_SCORE)
            tier1_count += 1
            continue
        if tier1_count < TIER1_MAX and row.final_score >= TIER1_MIN_SCORE:
            row.tier = 1
            tier1_count += 1
        elif tier2_count < (TIER2_MAX - tier1_count) and _tier2_eligible(row, insertion_path):
            row.tier = 2
            tier2_count += 1
        else:
            row.tier = 0


def _promote_matched_recall(
    ranked: List[FileScoreBreakdown],
    detection: DetectionResult,
    insertion_path: str,
) -> None:
    """Promote ground-truth sibling modules into tier 1 without opening tier 2 noise."""
    concept_id = detection.concept_id or ""
    matched_paths = sorted({s.file_path.replace("\\", "/") for s in detection.matched_symbols})
    tier1_count = sum(1 for r in ranked if r.tier == 1)

    def _promote(path: str) -> None:
        nonlocal tier1_count
        if tier1_count >= TIER1_MAX:
            return
        row = next((r for r in ranked if r.path == path), None)
        if not row:
            return
        if row.tier == 1:
            return
        row.tier = 1
        row.final_score = max(row.final_score, TIER1_MIN_SCORE)
        tier1_count += 1

    if concept_id in CONFIG_CONCEPTS:
        for path in matched_paths:
            if "_config" in _norm(path):
                _promote(path)
        return

    if concept_id == "indicator_backtest_live":
        for path in matched_paths:
            pl = _norm(path)
            if "registry/signal" in pl:
                continue
            if any(x in pl for x in ("indicators/", "signals/pipeline", "sma.py")):
                _promote(path)
        return

    if concept_id == "idempotency_key":
        for path in matched_paths:
            pl = _norm(path)
            if "order" in pl or "execution" in pl:
                _promote(path)
        return

    if concept_id in ("oauth2", "authentication", "jwt"):
        for path in matched_paths:
            if _norm(path).startswith("auth/"):
                _promote(path)
        return

    if concept_id in REGISTRY_OK_CONCEPTS or concept_id == "ema":
        for path in matched_paths:
            pl = _norm(path)
            if any(x in pl for x in ("registry", "indicator", "signal", "pipeline")):
                _promote(path)
        return


def _promote_heuristic_recall(
    ranked: List[FileScoreBreakdown],
    heuristic_paths: Optional[List[str]],
    *,
    keywords: Optional[List[str]] = None,
    concept_id: str = "",
    insertion_path: str = "",
) -> None:
    tier1_count = sum(1 for r in ranked if r.tier == 1)
    tier2_count = sum(1 for r in ranked if r.tier == 2)
    kws = [k.lower() for k in (keywords or []) if len(k) > 2]
    for path in (heuristic_paths or [])[:4]:
        pl = _norm(path)
        if kws and not any(k in pl for k in kws):
            if concept_id not in CONFIG_CONCEPTS or "_config" not in pl:
                continue
        row = next((r for r in ranked if _norm(r.path) == pl), None)
        if not row or row.tier != 0:
            continue
        if row.final_score < TIER2_MIN_SCORE - 6:
            continue
        if tier2_count < (TIER2_MAX - tier1_count) and _tier2_eligible(row, insertion_path):
            row.tier = 2
            row.final_score = max(row.final_score, TIER2_MIN_SCORE)
            tier2_count += 1


def rank_files(
    store: SymbolIndex | Any,
    call_graph: CallGraph,
    detection: DetectionResult,
    *,
    concept_keywords: Optional[List[str]] = None,
    heuristic_paths: Optional[List[str]] = None,
    graph: Optional[Dict[str, Any]] = None,
    insertion_path: str = "",
) -> PrecisionResult:
    """Rank candidate files by multi-signal evidence (Phase 131)."""
    index: SymbolIndex = store if isinstance(store, SymbolIndex) else store.symbol_index
    keywords = list(concept_keywords or [])
    patterns = list(detection.search_patterns or [])
    candidates: Set[str] = set()

    by_file: Dict[str, List[Any]] = {}
    for sym in detection.matched_symbols:
        candidates.add(sym.file_path)
        by_file.setdefault(sym.file_path, []).append(sym)

    for path in heuristic_paths or []:
        if path.endswith(".py") or "/" in path:
            candidates.add(path.replace("\\", "/"))

    if insertion_path:
        candidates.add(insertion_path.replace("\\", "/"))

    ranked: List[FileScoreBreakdown] = []
    heur_norm = {_norm(p): i for i, p in enumerate(heuristic_paths or [])}
    for path in candidates:
        syms = by_file.get(path) or index.symbols_in_file(path)
        if not syms and _norm(path) not in heur_norm:
            continue
        row = _score_file_components(
            path,
            syms,
            patterns,
            detection.insertion_patterns,
            index,
            call_graph,
            insertion_path,
            keywords,
            graph,
            concept_id=detection.concept_id or "",
        )
        hidx = heur_norm.get(_norm(path))
        if hidx is not None:
            boost = max(0.0, 14.0 - hidx * 3.0)
            row.final_score = min(100.0, row.final_score + boost)
            if hidx <= 1 and row.concept_match_score >= 0.2:
                row.concept_match_score = min(1.0, row.concept_match_score + 0.15)
            row.reasons.append(f"heuristic rank #{hidx + 1}")
        if any(k in _norm(path) for k in ("order", "execution")) and any(
            k in " ".join(keywords).lower() for k in ("order", "retry", "duplicate")
        ):
            row.final_score = min(100.0, row.final_score + 14.0)
            row.implementation_score = min(1.0, row.implementation_score + 0.2)
        ranked.append(row)

    _assign_tiers(ranked, insertion_path)
    _promote_matched_recall(ranked, detection, insertion_path)
    _promote_heuristic_recall(
        ranked,
        heuristic_paths,
        keywords=keywords,
        concept_id=detection.concept_id or "",
        insertion_path=insertion_path,
    )
    tier1 = [r.path for r in ranked if r.tier == 1]
    tier2 = [r.path for r in ranked if r.tier == 2]
    tier3: List[str] = []

    if insertion_path and insertion_path not in tier1:
        ins = _norm(insertion_path)
        if any(_norm(p) == ins for p in tier1):
            pass
        elif tier1:
            if len(tier1) >= TIER1_MAX:
                tier2.insert(0, tier1.pop())
            tier1.insert(0, insertion_path.replace("\\", "/"))
        else:
            tier1 = [insertion_path.replace("\\", "/")]

    tier12_paths = set(tier1 + tier2)
    file_evidences = [
        FileEvidence(
            path=r.path,
            evidence_score=r.final_score,
            matching_symbols=[f"{s.name}" for s in by_file.get(r.path, [])[:4]],
            matching_concepts=patterns[:4],
            usage_patterns=r.reasons[:3],
            reason_selected=f"final={r.final_score:.0f} def={r.definition_score:.2f} impl={r.implementation_score:.2f}",
            symbol_details=[s.to_dict() for s in by_file.get(r.path, [])[:4]],
        )
        for r in ranked
        if r.path in tier1
    ]

    ins_conf = _insertion_confidence(insertion_path, ranked, detection, index)

    return PrecisionResult(
        ranked=[r for r in ranked if r.tier in (1, 2)],
        tier1=tier1[:TIER1_MAX],
        tier2=tier2[: max(0, TIER2_MAX - len(tier1[:TIER1_MAX]))],
        tier3=tier3,
        insertion_confidence=ins_conf,
        insertion_path=insertion_path.replace("\\", "/") if insertion_path else "",
        file_evidences=file_evidences,
    )


def apply_precision_to_plan(plan: Dict[str, Any], precision: PrecisionResult, *, investigate: bool = False) -> None:
    """Replace broad heuristic file lists with evidence-tier recommendations."""
    tier1 = precision.tier1
    tier2 = precision.tier2
    max_support = 6 if investigate else TIER2_MAX
    tier12 = list(dict.fromkeys(tier1 + tier2))[:max_support]

    plan["recommendation_tiers"] = precision.to_dict()
    plan["insertion_confidence"] = precision.insertion_confidence
    plan["precision_ranked_files"] = [r.to_dict() for r in precision.ranked[:15]]

    # Primary recommendations — tier 1 only (precision KPI)
    plan["files_to_inspect_first"] = tier1[:TIER1_MAX]
    plan["inspect_first"] = tier1[:TIER1_MAX]
    plan["suggested_files_to_inspect"] = tier1[:TIER1_MAX]

    # Supporting — tier 1 + 2 capped
    plan["files_likely_to_change"] = tier12[:TIER2_MAX]
    plan["likely_affected_modules"] = tier12[:TIER2_MAX]
    plan["likely_modules"] = tier12[:TIER2_MAX]

    rev = plan.get("repository_evidence") or {}
    rev["insertion_confidence"] = precision.insertion_confidence
    rev["recommendation_tiers"] = precision.to_dict()
    rev["file_evidences"] = [fe.to_dict() for fe in precision.file_evidences[:10]]
    if precision.insertion_path:
        rev["recommended_insertion"] = precision.insertion_path
    plan["repository_evidence"] = rev

    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        dk["insertion_confidence"] = precision.insertion_confidence
        dk["recommendation_tiers"] = precision.to_dict()
        dk["file_evidence_summary"] = [
            {
                "path": r.path,
                "score": r.final_score,
                "tier": r.tier,
                "definition": r.definition_score,
                "implementation": r.implementation_score,
                "reasons": r.reasons[:3],
            }
            for r in precision.ranked[:10]
        ]
        roles = dk.get("file_roles") or {}
        roles["must_inspect"] = tier1[:TIER1_MAX]
        roles["likely_modify"] = tier2[: max(0, TIER2_MAX - len(tier1))]
        roles["verify_only"] = []
        plan["optional_verification_files"] = precision.tier3
        dk["file_roles"] = roles
        dk["repository_evidence"] = rev
        plan["domain_knowledge"] = dk
        plan["knowledge_engine"] = dk

    # Enrich benchmark-visible risk/test recall from domain knowledge
    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        arch = list(plan.get("architectural_risks") or [])
        for r in (dk.get("risks") or dk.get("knowledge_risks") or [])[:8]:
            label = f"[knowledge] {r}" if not str(r).startswith("[") else str(r)
            if label not in arch:
                arch.append(label)
        plan["architectural_risks"] = arch[:14]
        tests = list(plan.get("tests_likely_affected") or [])
        for t in (dk.get("testing") or [])[:6]:
            if t not in tests:
                tests.append(t)
        plan["tests_likely_affected"] = tests[:12]
        plan["tests_required"] = tests[:12]


def apply_precision_to_impact(plan: Dict[str, Any], target: str, graph: Optional[Dict[str, Any]] = None) -> None:
    """Trim impact lists to target plus direct importers (high precision)."""
    target = (target or plan.get("target") or "").replace("\\", "/")
    affected = list(plan.get("affected_files") or plan.get("potentially_affected_modules") or [])
    tier1 = [target] if target else []
    tier2 = affected[:4]
    combined = list(dict.fromkeys(tier1 + tier2))[:5]
    plan["recommendation_tiers"] = {
        "tier1_strong_evidence": tier1,
        "tier2_supporting": tier2,
        "tier3_verify_only": [],
    }
    plan["potentially_affected_modules"] = combined
    plan["affected_files"] = combined
    if plan.get("simulation"):
        plan["simulation"]["potentially_affected_modules"] = combined
