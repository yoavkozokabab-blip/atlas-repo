"""Phase 163 — symbol-level evidence collection for precision grounding."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .call_graph import CallGraph
from .evidence_models import SymbolRecord
from .symbol_index import SymbolIndex



@dataclass
class SymbolEvidence:
    name: str
    kind: str
    qualname: str = ""
    file_path: str = ""
    line: int = 0
    defined_here: bool = True
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePanel:
    matched_symbols: List[Dict[str, Any]] = field(default_factory=list)
    matched_references: List[Dict[str, Any]] = field(default_factory=list)
    graph_support: List[str] = field(default_factory=list)
    repository_evidence: List[str] = field(default_factory=list)
    selected_because: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def _terms_blob(terms: Iterable[str]) -> Set[str]:
    return {t.lower() for t in terms if t and len(t) > 2}


def _symbol_matches(sym: SymbolRecord, terms: Set[str], patterns: List[str]) -> bool:
    blob = " ".join([sym.name, sym.qualname or "", sym.kind]).lower()
    if terms and any(t in blob for t in terms):
        return True
    pats = [p.lower() for p in patterns if p]
    return any(p in blob for p in pats)


def _caller_labels(call_graph: CallGraph, sym: SymbolRecord) -> List[str]:
    keys = [sym.qualname, sym.name, f"{sym.file_path}::{sym.qualname or sym.name}"]
    seen: Set[str] = set()
    out: List[str] = []
    for key in keys:
        if not key:
            continue
        for caller in call_graph.who_calls(key):
            if caller not in seen:
                seen.add(caller)
                out.append(caller)
    return out[:6]


def _callee_labels(call_graph: CallGraph, sym: SymbolRecord) -> List[str]:
    caller_key = f"{sym.file_path}::{sym.qualname or sym.name}"
    return sorted(call_graph.callees.get(caller_key, set()))[:6]


def _index_and_graph(store_or_index: Any) -> Tuple[SymbolIndex, CallGraph]:
    if hasattr(store_or_index, "symbol_index"):
        return store_or_index.symbol_index, store_or_index.call_graph
    return store_or_index, CallGraph()


def file_symbol_evidence(
    store_or_index: Any,
    path: str,
    terms: Iterable[str],
    patterns: Optional[List[str]] = None,
) -> Tuple[List[SymbolEvidence], float]:
    """Collect symbol evidence for a file and return (evidences, boost_score 0–15)."""
    index, call_graph = _index_and_graph(store_or_index)
    path_norm = path.replace("\\", "/")
    term_set = _terms_blob(terms)
    pats = list(patterns or [])
    syms = index.symbols_in_file(path_norm)
    if not syms and not term_set and not pats:
        return [], 0.0

    matched: List[SymbolEvidence] = []
    for sym in syms:
        if not _symbol_matches(sym, term_set, pats):
            continue
        matched.append(
            SymbolEvidence(
                name=sym.name,
                kind=sym.kind,
                qualname=sym.qualname or sym.name,
                file_path=path_norm,
                line=sym.line,
                defined_here=True,
                callers=_caller_labels(call_graph, sym),
                callees=_callee_labels(call_graph, sym),
                references=[f"import/usage count {sym.usage_count}"] if sym.usage_count else [],
            )
        )

    boost = 0.0
    if matched:
        boost += min(10.0, 2.5 + len(matched) * 1.5)
        if any(s.kind in ("function", "class", "method") for s in matched):
            boost += 2.0
        if any(s.callers for s in matched):
            boost += 2.5
    return matched, boost


def symbol_boost_for_path(
    store_or_index: Any,
    path: str,
    terms: Iterable[str],
    patterns: Optional[List[str]] = None,
) -> Tuple[float, List[str]]:
    """Return (score_boost, reason_lines) for fused file ranking."""
    evidences, boost = file_symbol_evidence(store_or_index, path, terms, patterns)
    reasons: List[str] = []
    for ev in evidences[:3]:
        reasons.append(f"Symbol {ev.kind} `{ev.qualname}` defined here")
        if ev.callers:
            reasons.append(f"`{ev.qualname}` referenced by {ev.callers[0]}")
    if not reasons and boost > 0:
        reasons.append("Path + symbol index overlap")
    return boost, reasons


def why_selected_for_file(
    path: str,
    symbol_evidences: List[SymbolEvidence],
    *,
    path_reasons: Optional[List[str]] = None,
    insertion: bool = False,
) -> str:
    """Human-readable 'Selected because' line for a file."""
    parts: List[str] = []
    if insertion:
        parts.append("Recommended insertion point")
    for ev in symbol_evidences[:2]:
        parts.append(f"Symbol `{ev.qualname}` ({ev.kind}) defined here")
        if ev.callers:
            parts.append(f"`{ev.qualname}` referenced by {ev.callers[0]}")
    for r in (path_reasons or [])[:2]:
        if r not in parts:
            parts.append(r)
    if not parts:
        parts.append("Path keyword overlap with request/symptom")
    return " · ".join(parts[:4])


def graph_support_lines(
    call_graph: CallGraph,
    path: str,
    *,
    anchor_path: str = "",
) -> List[str]:
    """Call-graph evidence strings for a file."""
    p = path.replace("\\", "/")
    lines: List[str] = []
    deps = call_graph.who_depends_on_file(p)
    if deps:
        lines.append(f"Call graph: {len(deps)} dependent edge(s) from `{p}`")
    if anchor_path and _norm(anchor_path) != _norm(p):
        anchor_deps = call_graph.who_depends_on_file(anchor_path)
        if p in anchor_deps or any(_norm(d) == _norm(p) for d in anchor_deps):
            lines.append(f"Call graph reaches `{p}` from `{anchor_path}`")
    callers = call_graph.callees.get(f"{p}::<module>", set())
    if callers:
        lines.append(f"Module-level calls: {', '.join(sorted(callers)[:3])}")
    return lines[:4]


def build_evidence_panel(
    store: Optional[Any],
    paths: List[str],
    terms: Iterable[str],
    *,
    patterns: Optional[List[str]] = None,
    symptom: str = "",
    anchor_path: str = "",
) -> EvidencePanel:
    """Aggregate evidence panel for Build / Investigate / Impact outputs."""
    panel = EvidencePanel()
    if not store:
        panel.repository_evidence = ["No symbol index — path heuristics only"]
        return panel

    term_set = _terms_blob(terms)
    if symptom:
        import re
        for tok in re.findall(r"[a-z][a-z0-9_]{2,}", symptom.lower()):
            term_set.add(tok)

    for path in paths[:8]:
        syms, boost = file_symbol_evidence(store, path, term_set, patterns)
        for ev in syms[:4]:
            panel.matched_symbols.append(ev.to_dict())
            for caller in ev.callers[:2]:
                panel.matched_references.append(
                    {"symbol": ev.qualname, "reference": caller, "file": path}
                )
        panel.graph_support.extend(graph_support_lines(store.call_graph, path, anchor_path=anchor_path))
        if syms:
            panel.selected_because.append(why_selected_for_file(path, syms))
        elif boost > 0:
            panel.selected_because.append(f"`{path}` — path evidence matches symptom/request")

    if symptom and paths:
        panel.repository_evidence.append(f"Repository evidence matches symptom keywords in `{paths[0]}`")
    if panel.matched_symbols:
        panel.repository_evidence.append(f"{len(panel.matched_symbols)} symbol definition(s) matched")
    if panel.matched_references:
        panel.repository_evidence.append(f"{len(panel.matched_references)} caller/reference link(s)")
    if panel.graph_support:
        panel.repository_evidence.append("Call graph support present")
    if not panel.repository_evidence:
        panel.repository_evidence = ["Path overlap only — no symbol index hits"]

    # De-dupe while preserving order
    panel.graph_support = list(dict.fromkeys(panel.graph_support))[:8]
    panel.selected_because = list(dict.fromkeys(panel.selected_because))[:8]
    panel.repository_evidence = list(dict.fromkeys(panel.repository_evidence))[:6]
    return panel


def impact_symbol_blast(
    store: Any,
    target_path: str,
) -> Tuple[List[str], List[str], EvidencePanel]:
    """Prefer call-graph symbol references over directory heuristics for impact."""
    target = target_path.replace("\\", "/")
    panel = build_evidence_panel(store, [target], [], anchor_path=target)
    extra_files: List[str] = []
    extra_reasons: List[str] = []

    index, call_graph = _index_and_graph(store)
    syms = index.symbols_in_file(target)
    seen: Set[str] = set()
    for sym in syms[:12]:
        for caller in _caller_labels(call_graph, sym):
            file_part = caller.split("::", 1)[0]
            if file_part and file_part not in seen and _norm(file_part) != _norm(target):
                seen.add(file_part)
                extra_files.append(file_part)
                extra_reasons.append(f"Symbol `{sym.qualname}` caller: {caller}")

    for dep in call_graph.who_depends_on_file(target)[:8]:
        if dep not in seen:
            seen.add(dep)
            extra_files.append(dep)
            extra_reasons.append(f"Call graph dependency from `{target}`")

    panel.graph_support.extend(extra_reasons[:6])
    panel.selected_because.insert(0, f"Impact anchored on `{target}` via symbol + call graph")
    return extra_files[:12], extra_reasons[:8], panel


def store_from_ctx(ctx: Dict[str, Any]) -> Optional[Any]:
    raw = ctx.get("evidence_store") or {}
    if not raw or not raw.get("symbol_index"):
        return None
    from .evidence_builder import EvidenceStore

    return EvidenceStore.from_dict(raw)
