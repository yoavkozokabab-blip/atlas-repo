"""Phase 96B read-only contract fact quality audit (measurement only)."""

from __future__ import annotations

import ast
import json
import os
import random
import textwrap
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from builder_core.bug_intelligence import callgraph, contract_facts, facts, summaries

# Audit labels
CORRECT = "correct"
PARTIAL = "partially_correct"
WRONG = "wrong"
TOO_WEAK = "too_weak_to_use"

SYNTHETIC_FIXTURES: List[Tuple[str, str]] = [
    ("synth_hint.py", textwrap.dedent("""
        def fetch() -> str:
            return "ok"
        def opt() -> str | None:
            return None
        def run(name: str) -> None:
            print(name)
    """)),
    ("synth_doc.py", textwrap.dedent("""
        def run(x):
            '''Run.

            Returns:
                A string result, never None.

            Raises:
                ValueError: bad input.
            '''
            if not x:
                raise ValueError(x)
            return str(x)
    """)),
    ("synth_assert.py", textwrap.dedent("""
        def run(x):
            assert x is not None
            return x.upper()
        class C:
            def go(self):
                assert self.buf is not None
                return self.buf
    """)),
    ("synth_caller.py", textwrap.dedent("""
        def helper():
            return 1
        def deref_caller():
            return helper().real
        def guarded_caller():
            v = helper()
            if v is None:
                return 0
            return v
    """)),
    ("synth_callee.py", textwrap.dedent("""
        def run(name):
            return name.upper()
        class Worker:
            def __init__(self):
                self.tag = "x"
            def show(self):
                return self.tag
    """)),
    ("synth_guard.py", textwrap.dedent("""
        def run(x):
            if x is not None:
                return x.upper()
            return ""
        def maybe(y):
            if y is None:
                return 0
            return y
    """)),
]

LOCAL_JARVIS_SAMPLES = [
    "core/results.py",
    "brain/router.py",
    "actions/phase45_actions.py",
    "builder_core/bug_intelligence/fact_detectors.py",
    "builder_core/bug_intelligence/contract_facts.py",
]

QUIXBUGS_ROOTS = [
    r"C:\Repos\QuixBugs",
    os.path.join("..", "QuixBugs"),
]


def _extract_from_source(text: str, rel: str, *, test_docs: Optional[List] = None) -> Dict[str, Any]:
    tree = ast.parse(text)
    mf = facts.extract_module_facts(text, rel, test_documents=test_docs or [])
    cg = callgraph.build_call_graph(tree, rel)
    mf["interproc"] = {"call_graph": cg, "summaries": summaries.compute_summaries(mf, cg)}
    return contract_facts.extract_module_contracts(mf, tree, rel)


def _all_records(contracts: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for k in (
        "return_contracts",
        "argument_contracts",
        "nullability_contracts",
        "exception_contracts",
        "state_mutation_contracts",
    ):
        out.extend(contracts.get(k, []) or [])
    seen = set()
    deduped = []
    for rec in out:
        key = json.dumps(rec, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            deduped.append(rec)
    return deduped


def _fn_node(tree: ast.AST, qualname: str) -> Optional[ast.AST]:
    qn = callgraph._compute_qualnames(tree)
    for node, q in qn.items():
        if q == qualname:
            return node
    return None


def _audit_fact(rec: Dict[str, Any], tree: ast.AST, text: str) -> Tuple[str, str]:
    """Return (label, reason). Rule-based auditor aligned with Phase 96 design."""
    src = (rec.get("sources") or [""])[0]
    obl = rec.get("obligation", "")
    conf = rec.get("confidence", "")
    subj = rec.get("subject", {})
    qual = subj.get("qualname", "")
    slot = subj.get("slot", "")
    fn = _fn_node(tree, qual)

    if src == contract_facts.SOURCE_TYPE_HINT:
        if fn is None and qual != "*":
            return WRONG, "subject qualname not found in AST"
        if obl == "return.non_none":
            ret = getattr(fn, "returns", None) if fn else None
            allows = contract_facts._annotation_allows_none(ret)
            if allows is False:
                return CORRECT, "annotation disallows None"
            if allows is True:
                return WRONG, "annotation allows None but fact says non_none"
            return PARTIAL, "annotation ambiguous (Any/Union) mapped to shape_uniform or unknown"
        if obl == "return.optional":
            ret = getattr(fn, "returns", None) if fn else None
            if contract_facts._annotation_allows_none(ret) is True:
                return CORRECT, "optional annotation"
            return WRONG, "non-optional annotation marked optional"
        if obl == "arg.non_none":
            return CORRECT, "non-optional param annotation"
        if obl == "arg.type_bound":
            return CORRECT, "type bound from annotation"
        return PARTIAL, "unreviewed type_hint obligation"

    if src == contract_facts.SOURCE_DOCSTRING:
        if obl == "raises.documented" and rec.get("exceptions"):
            return CORRECT, "structured Raises section parsed"
        if obl in ("return.non_none", "return.optional"):
            doc = ast.get_docstring(fn) if fn else ""
            if not doc:
                return WRONG, "docstring missing"
            low = doc.lower()
            if obl == "return.optional" and "none" in low:
                return PARTIAL, "free-text None mention; not structured proof"
            if obl == "return.non_none":
                return PARTIAL, "Returns section heuristic; may over-claim non_none"
        return PARTIAL, "docstring heuristic"

    if src == contract_facts.SOURCE_ASSERT:
        if obl in ("arg.non_none", "null.forbidden"):
            return CORRECT, "assert-is-not-None is explicit local proof"
        if obl == "state.initialized_before_read":
            return PARTIAL, "assert documents intent at point, not lifecycle invariant"
        return CORRECT, "assert-backed"

    if src == contract_facts.SOURCE_TEST:
        return TOO_WEAK, "repository-level test expectation; weak by design"

    if src == contract_facts.SOURCE_CALLER_BEHAVIOR:
        if conf == contract_facts.CONFIDENCE_INFERRED_STRONG and obl == "return.non_none":
            return PARTIAL, "usage implies non-None need; not API contract"
        if conf == contract_facts.CONFIDENCE_INFERRED_WEAK:
            return TOO_WEAK, "mixed/null-check caller evidence"
        return PARTIAL, "caller usage inference"

    if src == contract_facts.SOURCE_CALLEE_BEHAVIOR:
        if obl == "arg.non_none" and slot.startswith("param:"):
            return PARTIAL, "callee derefs param; callers may still pass None"
        if obl == "state.initialized_before_read":
            return PARTIAL, "__init__ assign + read; early __init__ exit not modeled"
        return PARTIAL, "callee behavior inference"

    if src == contract_facts.SOURCE_GUARD:
        if obl == "null.narrowed_by_guard":
            return PARTIAL, "true only on guarded branch dominator unproven"
        if obl == "null.checked_before_use":
            return PARTIAL, "None-branch only; other paths may remain unsafe"
        if obl in ("null.forbidden", "null.allowed"):
            if any(ref.get("fact_state") for ref in rec.get("evidence_refs") or []):
                return PARTIAL, "valueflow fact within function; path-insensitive"
            return PARTIAL, "guard fact without path feasibility"
        return PARTIAL, "guard-derived"

    if conf == contract_facts.CONFIDENCE_UNKNOWN:
        return TOO_WEAK, "unknown confidence"
    return PARTIAL, "default conservative partial"


def audit_corpus(name: str, items: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    labels_by_source: Dict[str, Counter] = defaultdict(Counter)
    labels_by_type: Dict[str, Counter] = defaultdict(Counter)
    samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    wrong_causes: Counter = Counter()

    for rel, text in items:
        try:
            tree = ast.parse(text)
            contracts = _extract_from_source(text, rel)
        except SyntaxError as exc:
            continue
        for rec in _all_records(contracts):
            label, reason = _audit_fact(rec, tree, text)
            src = (rec.get("sources") or ["?"])[0]
            ctype = rec.get("contract_type", "?")
            labels_by_source[src][label] += 1
            labels_by_type[ctype][label] += 1
            rec_copy = {
                "file": rel,
                "qualname": rec.get("subject", {}).get("qualname"),
                "slot": rec.get("subject", {}).get("slot"),
                "obligation": rec.get("obligation"),
                "confidence": rec.get("confidence"),
                "source": src,
                "audit": label,
                "reason": reason,
            }
            records.append(rec_copy)
            if label == WRONG:
                wrong_causes[reason] += 1
            if len(samples[src]) < 5:
                samples[src].append(rec_copy)

    def precision(counter: Counter) -> Dict[str, Any]:
        total = sum(counter.values())
        correct = counter[CORRECT]
        partial = counter[PARTIAL]
        wrong = counter[WRONG]
        weak = counter[TOO_WEAK]
        usable = correct + partial
        return {
            "total": total,
            "correct": correct,
            "partially_correct": partial,
            "wrong": wrong,
            "too_weak": weak,
            "strict_precision": round(correct / total, 4) if total else None,
            "usable_precision": round(usable / total, 4) if total else None,
        }

    by_source = {src: precision(cnt) for src, cnt in sorted(labels_by_source.items())}
    by_type = {t: precision(cnt) for t, cnt in sorted(labels_by_type.items())}

    return {
        "corpus": name,
        "fact_count": len(records),
        "by_source": by_source,
        "by_type": by_type,
        "wrong_causes": dict(wrong_causes.most_common(10)),
        "samples_by_source": samples,
    }


def _read_local(path: str, root: str) -> Optional[str]:
    full = os.path.join(root, path.replace("/", os.sep))
    if not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8-sig", errors="ignore") as fh:
        return fh.read()


def _quixbugs_files(root: str, n: int = 12) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for sub in ("correct_python_programs", "python_programs"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if fname.endswith(".py"):
                rel = f"{sub}/{fname}"
                text = _read_local(rel, root)
                if text:
                    out.append((rel, text))
                if len(out) >= n:
                    return out
    return out


def _local_jarvis_scan(root: str, max_files: int = 80) -> Dict[str, Any]:
    """Scan a broader file slice for source-volume statistics."""
    from builder_core.bug_intelligence import depgraph

    files = depgraph._collect_files(root)[:max_files]
    source_counts: Counter = Counter()
    type_counts: Counter = Counter()
    total = 0
    for rel, text in files:
        try:
            contracts = _extract_from_source(text, rel)
        except SyntaxError:
            continue
        for rec in _all_records(contracts):
            total += 1
            type_counts[rec.get("contract_type", "?")] += 1
            for src in rec.get("sources") or []:
                source_counts[src] += 1
    return {
        "files_scanned": len(files),
        "fact_count": total,
        "by_source_volume": dict(source_counts.most_common()),
        "by_type_volume": dict(type_counts.most_common()),
    }


def run_audit(local_root: str = ".") -> Dict[str, Any]:
    random.seed(96)

    synth = audit_corpus("synthetic", SYNTHETIC_FIXTURES)

    local_items = []
    for rel in LOCAL_JARVIS_SAMPLES:
        text = _read_local(rel, local_root)
        if text:
            local_items.append((rel, text))
    local = audit_corpus("local_jarvis", local_items)

    quix_items: List[Tuple[str, str]] = []
    quix_root = None
    for root in QUIXBUGS_ROOTS:
        if os.path.isdir(root):
            quix_root = os.path.abspath(root)
            quix_items = _quixbugs_files(quix_root, n=24)
            break
    quix = audit_corpus("quixbugs", quix_items) if quix_items else {
        "corpus": "quixbugs",
        "available": False,
        "fact_count": 0,
    }

    # aggregate across corpora with data
    agg_source: Dict[str, Counter] = defaultdict(Counter)
    agg_type: Dict[str, Counter] = defaultdict(Counter)
    for corp in (synth, local, quix):
        if corp.get("available") is False:
            continue
        for src, metrics in corp.get("by_source", {}).items():
            for label in (CORRECT, PARTIAL, WRONG, TOO_WEAK):
                agg_source[src][label] += metrics.get(label, 0)
        for t, metrics in corp.get("by_type", {}).items():
            for label in (CORRECT, PARTIAL, WRONG, TOO_WEAK):
                agg_type[t][label] += metrics.get(label, 0)

    def precision(counter: Counter) -> Dict[str, Any]:
        total = sum(counter.values())
        correct = counter[CORRECT]
        partial = counter[PARTIAL]
        return {
            "total": total,
            "strict_precision": round(correct / total, 4) if total else None,
            "usable_precision": round((correct + partial) / total, 4) if total else None,
        }

    return {
        "synthetic": synth,
        "local_jarvis": local,
        "local_jarvis_volume_scan": _local_jarvis_scan(local_root),
        "quixbugs": quix,
        "aggregate_by_source": {k: precision(v) for k, v in sorted(agg_source.items())},
        "aggregate_by_type": {k: precision(v) for k, v in sorted(agg_type.items())},
        "quixbugs_root": quix_root,
    }


if __name__ == "__main__":
    print(json.dumps(run_audit("."), indent=2, sort_keys=True))
