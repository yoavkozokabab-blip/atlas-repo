"""Contract fact extraction infrastructure (Phase 96A).

Extracts deterministic contract *facts* from type hints, docstrings, asserts,
tests, caller/callee behavior, and guards. Facts are attached to the module fact
model for inspection and future confirmation evaluators.

This module emits NO findings, performs NO promotion, and is consumed by NO
detector in Phase 96A.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from . import callgraph

# Feature flag — set False to omit contract facts from analysis output.
CONTRACT_FACTS_ENABLED = True

# Contract type identifiers (stored on each record as ``contract_type``).
RETURN_CONTRACT = "return_contract"
ARGUMENT_CONTRACT = "argument_contract"
NULLABILITY_CONTRACT = "nullability_contract"
EXCEPTION_CONTRACT = "exception_contract"
STATE_MUTATION_CONTRACT = "state_mutation_contract"

CONTRACT_TYPES = (
    RETURN_CONTRACT,
    ARGUMENT_CONTRACT,
    NULLABILITY_CONTRACT,
    EXCEPTION_CONTRACT,
    STATE_MUTATION_CONTRACT,
)

# Confidence levels (Phase 96 design §4).
CONFIDENCE_EXPLICIT = "explicit"
CONFIDENCE_INFERRED_STRONG = "inferred_strong"
CONFIDENCE_INFERRED_WEAK = "inferred_weak"
CONFIDENCE_UNKNOWN = "unknown"

CONFIDENCE_LEVELS = (
    CONFIDENCE_EXPLICIT,
    CONFIDENCE_INFERRED_STRONG,
    CONFIDENCE_INFERRED_WEAK,
    CONFIDENCE_UNKNOWN,
)

# Source tags (Phase 96 design §3).
SOURCE_TYPE_HINT = "type_hint"
SOURCE_DOCSTRING = "docstring"
SOURCE_ASSERT = "assert"
SOURCE_TEST = "test"
SOURCE_CALLER_BEHAVIOR = "caller_behavior"
SOURCE_CALLEE_BEHAVIOR = "callee_behavior"
SOURCE_GUARD = "guard"

_SCOPE_INTRA_FILE = "intra_file"


def _record(
    *,
    contract_type: str,
    file: str,
    qualname: str,
    slot: str,
    obligation: str,
    confidence: str,
    sources: List[str],
    evidence_refs: List[Dict[str, Any]],
    scope: str = _SCOPE_INTRA_FILE,
    exceptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "contract_type": contract_type,
        "subject": {"file": file, "qualname": qualname, "slot": slot},
        "obligation": obligation,
        "confidence": confidence,
        "sources": sorted(set(sources)),
        "evidence_refs": evidence_refs,
        "scope": scope,
        "exceptions": list(exceptions or []),
    }


def _ev(source: str, line: int, **extra: Any) -> Dict[str, Any]:
    ref: Dict[str, Any] = {"source": source, "line": line}
    ref.update(extra)
    return ref


def _unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _annotation_allows_none(node: Optional[ast.AST]) -> Optional[bool]:
    """Return True/False if nullability is known; None if unknown (Any, bare Name)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name) and node.id in ("None", "NoneType"):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = node.left, node.right
        if _annotation_allows_none(left) or _annotation_allows_none(right):
            return True
        if _annotation_allows_none(left) is False and _annotation_allows_none(right) is False:
            return False
        return None
    if isinstance(node, ast.Subscript):
        base = _unparse(node.value)
        if base in ("Optional", "typing.Optional"):
            return True
        if base in ("Union", "typing.Union"):
            return None
    if isinstance(node, ast.Name) and node.id == "Any":
        return None
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
        return False
    return None


def _iter_functions(tree: ast.AST) -> List[Tuple[ast.AST, str]]:
    qualnames = callgraph._compute_qualnames(tree)
    return sorted(qualnames.items(), key=lambda kv: kv[1])


def _extract_type_hints(
    tree: ast.AST, file: str
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    returns: List[Dict] = []
    arguments: List[Dict] = []
    nullability: List[Dict] = []

    for fn_node, qual in _iter_functions(tree):
        line = getattr(fn_node, "lineno", 0)
        ret_ann = getattr(fn_node, "returns", None)
        if ret_ann is not None:
            allows = _annotation_allows_none(ret_ann)
            if allows is True:
                obligation = "return.optional"
            elif allows is False:
                obligation = "return.non_none"
            else:
                obligation = "return.shape_uniform"
            confidence = (
                CONFIDENCE_EXPLICIT if allows is not None else CONFIDENCE_UNKNOWN
            )
            returns.append(_record(
                contract_type=RETURN_CONTRACT,
                file=file,
                qualname=qual,
                slot="return",
                obligation=obligation,
                confidence=confidence,
                sources=[SOURCE_TYPE_HINT],
                evidence_refs=[_ev(SOURCE_TYPE_HINT, line, annotation=_unparse(ret_ann))],
            ))
            if allows is True:
                nullability.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot="return",
                    obligation="null.allowed",
                    confidence=CONFIDENCE_EXPLICIT,
                    sources=[SOURCE_TYPE_HINT],
                    evidence_refs=[_ev(SOURCE_TYPE_HINT, line, annotation=_unparse(ret_ann))],
                ))
            elif allows is False:
                nullability.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot="return",
                    obligation="null.forbidden",
                    confidence=CONFIDENCE_EXPLICIT,
                    sources=[SOURCE_TYPE_HINT],
                    evidence_refs=[_ev(SOURCE_TYPE_HINT, line, annotation=_unparse(ret_ann))],
                ))

        args = getattr(fn_node, "args", None)
        if args is None:
            continue
        all_args = list(args.posonlyargs) + list(args.args)
        if args.vararg:
            all_args.append(args.vararg)
        for arg in all_args:
            if arg.arg in ("self", "cls"):
                continue
            ann = arg.annotation
            if ann is None:
                continue
            allows = _annotation_allows_none(ann)
            aline = getattr(arg, "lineno", line)
            arguments.append(_record(
                contract_type=ARGUMENT_CONTRACT,
                file=file,
                qualname=qual,
                slot=f"param:{arg.arg}",
                obligation="arg.type_bound",
                confidence=CONFIDENCE_EXPLICIT,
                sources=[SOURCE_TYPE_HINT],
                evidence_refs=[_ev(SOURCE_TYPE_HINT, aline, annotation=_unparse(ann))],
            ))
            if allows is False:
                arguments.append(_record(
                    contract_type=ARGUMENT_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot=f"param:{arg.arg}",
                    obligation="arg.non_none",
                    confidence=CONFIDENCE_EXPLICIT,
                    sources=[SOURCE_TYPE_HINT],
                    evidence_refs=[_ev(SOURCE_TYPE_HINT, aline, annotation=_unparse(ann))],
                ))
                nullability.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot=f"param:{arg.arg}",
                    obligation="null.forbidden",
                    confidence=CONFIDENCE_EXPLICIT,
                    sources=[SOURCE_TYPE_HINT],
                    evidence_refs=[_ev(SOURCE_TYPE_HINT, aline, annotation=_unparse(ann))],
                ))
            elif allows is True:
                nullability.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot=f"param:{arg.arg}",
                    obligation="null.allowed",
                    confidence=CONFIDENCE_EXPLICIT,
                    sources=[SOURCE_TYPE_HINT],
                    evidence_refs=[_ev(SOURCE_TYPE_HINT, aline, annotation=_unparse(ann))],
                ))

    return returns, arguments, nullability


_DOC_SECTION = re.compile(
    r"^(Args?|Arguments?|Parameters?|Returns?|Return|Raises?|Raises)\s*:\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_docstring_sections(doc: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    if not doc:
        return sections
    matches = list(_DOC_SECTION.finditer(doc))
    for i, match in enumerate(matches):
        name = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc)
        sections[name.rstrip("s")] = doc[start:end].strip()
        if name.startswith("arg"):
            sections["args"] = sections[name.rstrip("s")]
    return sections


def _extract_docstrings(
    tree: ast.AST, file: str
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    returns: List[Dict] = []
    arguments: List[Dict] = []
    exceptions: List[Dict] = []

    for fn_node, qual in _iter_functions(tree):
        doc = ast.get_docstring(fn_node) or ""
        if not doc.strip():
            continue
        line = getattr(fn_node, "lineno", 0)
        sections = _parse_docstring_sections(doc)
        if "return" in sections:
            body = sections["return"].lower()
            if "none" in body and "not none" not in body:
                obligation = "return.optional"
            else:
                obligation = "return.non_none"
            returns.append(_record(
                contract_type=RETURN_CONTRACT,
                file=file,
                qualname=qual,
                slot="return",
                obligation=obligation,
                confidence=CONFIDENCE_EXPLICIT,
                sources=[SOURCE_DOCSTRING],
                evidence_refs=[_ev(SOURCE_DOCSTRING, line, section="Returns")],
            ))
        if "args" in sections or "arg" in sections:
            args_text = sections.get("args") or sections.get("arg") or ""
            for param_line in args_text.splitlines():
                m = re.match(r"^\s*(\w+)\s*:", param_line)
                if not m:
                    continue
                param = m.group(1)
                lower = param_line.lower()
                if "must not be none" in lower or "non-none" in lower:
                    arguments.append(_record(
                        contract_type=ARGUMENT_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"param:{param}",
                        obligation="arg.non_none",
                        confidence=CONFIDENCE_EXPLICIT,
                        sources=[SOURCE_DOCSTRING],
                        evidence_refs=[_ev(SOURCE_DOCSTRING, line, param=param),
                        ],
                    ))
        if "raise" in sections:
            for exc_line in sections["raise"].splitlines():
                exc_line = exc_line.strip()
                if not exc_line or exc_line.startswith("-"):
                    continue
                exc_name = exc_line.split(":", 1)[0].strip().split()[0]
                if exc_name:
                    exceptions.append(_record(
                        contract_type=EXCEPTION_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot="raises",
                        obligation="raises.documented",
                        confidence=CONFIDENCE_EXPLICIT,
                        sources=[SOURCE_DOCSTRING],
                        evidence_refs=[
                            _ev(SOURCE_DOCSTRING, line, exception=exc_name),
                        ],
                        exceptions=[exc_name],
                    ))

    return returns, arguments, exceptions


def _is_none_compare(node: ast.AST, name: str, *, negated: bool = False) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    ops_ok = any(isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)) for op in node.ops)
    if not ops_ok:
        return False
    operands = [node.left, *node.comparators]
    has_none = any(isinstance(o, ast.Constant) and o.value is None for o in operands)
    has_name = any(isinstance(o, ast.Name) and o.id == name for o in operands)
    if not (has_none and has_name):
        return False
    if negated:
        return any(isinstance(op, (ast.IsNot, ast.NotEq)) for op in node.ops)
    return any(isinstance(op, (ast.Is, ast.Eq)) for op in node.ops)


def _is_not_none_check(test: ast.AST, target: ast.AST) -> bool:
    if not isinstance(test, ast.Compare):
        return False
    operands = [test.left, *test.comparators]
    if target not in operands:
        return False
    has_none = any(isinstance(o, ast.Constant) and o.value is None for o in operands)
    if not has_none:
        return False
    return any(isinstance(op, (ast.IsNot, ast.NotEq)) for op in test.ops)


def _extract_asserts(
    tree: ast.AST, file: str
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    arguments: List[Dict] = []
    nullability: List[Dict] = []
    state: List[Dict] = []

    for fn_node, qual in _iter_functions(tree):
        for node in callgraph._walk_local(fn_node):
            if not isinstance(node, ast.Assert):
                continue
            line = getattr(node, "lineno", 0)
            test = node.test
            if not isinstance(test, ast.Compare):
                continue
            for side in (test.left, *test.comparators):
                if isinstance(side, ast.Name) and _is_none_compare(test, side.id, negated=True):
                    arguments.append(_record(
                        contract_type=ARGUMENT_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"param:{side.id}",
                        obligation="arg.non_none",
                        confidence=CONFIDENCE_EXPLICIT,
                        sources=[SOURCE_ASSERT],
                        evidence_refs=[_ev(SOURCE_ASSERT, line)],
                    ))
                    nullability.append(_record(
                        contract_type=NULLABILITY_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"local:{side.id}",
                        obligation="null.forbidden",
                        confidence=CONFIDENCE_EXPLICIT,
                        sources=[SOURCE_ASSERT],
                        evidence_refs=[_ev(SOURCE_ASSERT, line)],
                    ))
                if (
                    isinstance(side, ast.Attribute)
                    and isinstance(side.value, ast.Name)
                    and side.value.id == "self"
                    and _is_not_none_check(test, side)
                ):
                    state.append(_record(
                        contract_type=STATE_MUTATION_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"state:{side.attr}",
                        obligation="state.initialized_before_read",
                        confidence=CONFIDENCE_EXPLICIT,
                        sources=[SOURCE_ASSERT],
                        evidence_refs=[_ev(SOURCE_ASSERT, line)],
                    ))

    return [], arguments, nullability, state


def _extract_state_init(tree: ast.AST, file: str) -> List[Dict]:
    """Fields assigned in ``__init__`` imply initialization before other methods read them."""
    init_fields: Dict[str, Set[str]] = {}

    for fn_node, qual in _iter_functions(tree):
        if fn_node.name != "__init__":
            continue
        class_base = qual.rsplit(".", 1)[0] if "." in qual else ""
        fields: Set[str] = set()
        for node in callgraph._walk_local(fn_node):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "self":
                            fields.add(target.attr)
        init_fields[class_base] = fields

    out: List[Dict] = []
    for fn_node, qual in _iter_functions(tree):
        if fn_node.name == "__init__":
            continue
        class_base = qual.rsplit(".", 1)[0] if "." in qual else ""
        fields = init_fields.get(class_base, set())
        emitted: Set[str] = set()
        for node in callgraph._walk_local(fn_node):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "self" and node.attr in fields:
                    key = f"{qual}:{node.attr}"
                    if key in emitted:
                        continue
                    emitted.add(key)
                    line = getattr(node, "lineno", 0)
                    out.append(_record(
                        contract_type=STATE_MUTATION_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"state:{node.attr}",
                        obligation="state.initialized_before_read",
                        confidence=CONFIDENCE_INFERRED_WEAK,
                        sources=[SOURCE_CALLEE_BEHAVIOR],
                        evidence_refs=[_ev(SOURCE_CALLEE_BEHAVIOR, line, field=node.attr)],
                    ))
    return out


def _extract_tests(module_facts: Dict[str, Any], file: str) -> List[Dict]:
    out: List[Dict] = []
    for exp in module_facts.get("test_expectations") or []:
        etype = exp.get("type", "")
        if not etype:
            continue
        obligation_map = {
            "returns_false_when_unreachable": ("return.non_none", CONFIDENCE_INFERRED_WEAK),
            "returns_true_when_reachable": ("return.non_none", CONFIDENCE_INFERRED_WEAK),
            "handles_cycles": ("return.shape_uniform", CONFIDENCE_INFERRED_WEAK),
        }
        mapped = obligation_map.get(etype)
        if mapped is None:
            continue
        obligation, confidence = mapped
        out.append(_record(
            contract_type=RETURN_CONTRACT,
            file=file,
            qualname="*",
            slot="return",
            obligation=obligation,
            confidence=confidence,
            sources=[SOURCE_TEST],
            evidence_refs=[_ev(SOURCE_TEST, 0, test_type=etype, source=exp.get("source", ""))],
            scope="repository",
        ))
    return out


def _caller_usage_facts(interproc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cg = interproc.get("call_graph") or {}
    usage_agg = cg.get("usage_by_callee") or {}
    per_callee: Dict[str, Dict[str, Any]] = {}

    for cs in cg.get("call_sites") or []:
        if not cs.get("resolved"):
            continue
        callee = cs.get("callee")
        if not callee:
            continue
        bucket = per_callee.setdefault(callee, {
            "deref_sites": [],
            "null_check_sites": [],
            "use_sites": [],
            "unresolved_callers": 0,
        })
        usage = cs.get("usage")
        entry = {"caller": cs.get("caller"), "line": cs.get("line"), "usage": usage}
        if usage == callgraph.DEREFERENCED:
            bucket["deref_sites"].append(entry)
        elif usage == callgraph.NULL_CHECKED:
            bucket["null_check_sites"].append(entry)
        elif usage in (callgraph.USED_VALUE, callgraph.RETURNED):
            bucket["use_sites"].append(entry)

    for callee, agg in usage_agg.items():
        per_callee.setdefault(callee, {
            "deref_sites": [],
            "null_check_sites": [],
            "use_sites": [],
            "unresolved_callers": 0,
        })
        merged = per_callee[callee]
        if agg.get("dereferenced") and not merged["deref_sites"]:
            merged["deref_sites"].append({"caller": "?", "line": 0, "usage": "dereferenced"})
        if agg.get("null_checked") and not merged["null_check_sites"]:
            merged["null_check_sites"].append({"caller": "?", "line": 0, "usage": "null_checked"})

    return per_callee


def _extract_caller_behavior(interproc: Optional[Dict[str, Any]], file: str) -> List[Dict]:
    if not interproc:
        return []
    out: List[Dict] = []
    for callee, info in _caller_usage_facts(interproc).items():
        deref = info.get("deref_sites") or []
        null_check = info.get("null_check_sites") or []
        if not deref and not null_check:
            continue
        if deref and not null_check:
            confidence = CONFIDENCE_INFERRED_STRONG
            obligation = "return.non_none"
        elif null_check and not deref:
            confidence = CONFIDENCE_INFERRED_WEAK
            obligation = "return.optional"
        else:
            confidence = CONFIDENCE_INFERRED_WEAK
            obligation = "return.non_none"
        refs = [
            _ev(SOURCE_CALLER_BEHAVIOR, s.get("line", 0), caller=s.get("caller"))
            for s in deref + null_check
        ]
        out.append(_record(
            contract_type=RETURN_CONTRACT,
            file=file,
            qualname=callee,
            slot="return",
            obligation=obligation,
            confidence=confidence,
            sources=[SOURCE_CALLER_BEHAVIOR],
            evidence_refs=refs,
        ))
        if deref and not null_check:
            out.append(_record(
                contract_type=NULLABILITY_CONTRACT,
                file=file,
                qualname=callee,
                slot="return",
                obligation="null.forbidden",
                confidence=confidence,
                sources=[SOURCE_CALLER_BEHAVIOR],
                evidence_refs=refs,
            ))
    return out


def _param_used_unguarded(fn_node: ast.AST, param: str) -> bool:
    guarded = False
    used = False
    for node in callgraph._walk_local(fn_node):
        if isinstance(node, ast.If):
            if _is_none_compare(node.test, param) or _is_none_compare(node.test, param, negated=True):
                guarded = True
        if isinstance(node, ast.Assert) and _is_none_compare(node.test, param, negated=True):
            guarded = True
        if isinstance(node, ast.Name) and node.id == param and isinstance(node.ctx, ast.Load):
            parent = getattr(node, "_cg_parent", None)
            if isinstance(parent, (ast.Attribute, ast.Subscript, ast.Call)):
                used = True
    return used and not guarded


def _extract_callee_behavior(tree: ast.AST, file: str) -> Tuple[List[Dict], List[Dict]]:
    callgraph._attach_parents(tree)
    arguments: List[Dict] = []
    nullability: List[Dict] = []

    for fn_node, qual in _iter_functions(tree):
        args = getattr(fn_node, "args", None)
        if args is None:
            continue
        for arg in list(args.args) + list(args.kwonlyargs):
            name = arg.arg
            if name in ("self", "cls"):
                continue
            if not _param_used_unguarded(fn_node, name):
                continue
            line = getattr(arg, "lineno", getattr(fn_node, "lineno", 0))
            arguments.append(_record(
                contract_type=ARGUMENT_CONTRACT,
                file=file,
                qualname=qual,
                slot=f"param:{name}",
                obligation="arg.non_none",
                confidence=CONFIDENCE_INFERRED_STRONG,
                sources=[SOURCE_CALLEE_BEHAVIOR],
                evidence_refs=[_ev(SOURCE_CALLEE_BEHAVIOR, line, param=name)],
            ))
            nullability.append(_record(
                contract_type=NULLABILITY_CONTRACT,
                file=file,
                qualname=qual,
                slot=f"param:{name}",
                obligation="null.forbidden",
                confidence=CONFIDENCE_INFERRED_STRONG,
                sources=[SOURCE_CALLEE_BEHAVIOR],
                evidence_refs=[_ev(SOURCE_CALLEE_BEHAVIOR, line, param=name)],
            ))
    return arguments, nullability


def _extract_guards(
    module_facts: Dict[str, Any], tree: ast.AST, file: str
) -> List[Dict]:
    out: List[Dict] = []
    callgraph._attach_parents(tree)

    for fn_node, qual in _iter_functions(tree):
        for node in callgraph._walk_local(fn_node):
            if not isinstance(node, ast.If):
                continue
            line = getattr(node, "lineno", 0)
            tested = node.test
            if isinstance(tested, ast.Name):
                if _is_none_compare(tested, tested.id, negated=True):
                    out.append(_record(
                        contract_type=NULLABILITY_CONTRACT,
                        file=file,
                        qualname=qual,
                        slot=f"local:{tested.id}",
                        obligation="null.narrowed_by_guard",
                        confidence=CONFIDENCE_INFERRED_STRONG,
                        sources=[SOURCE_GUARD],
                        evidence_refs=[_ev(SOURCE_GUARD, line, guard="is_not_none"),
                        ],
                    ))
            elif isinstance(tested, ast.Compare):
                for side in (tested.left, *tested.comparators):
                    if isinstance(side, ast.Name) and _is_none_compare(tested, side.id, negated=True):
                        out.append(_record(
                            contract_type=NULLABILITY_CONTRACT,
                            file=file,
                            qualname=qual,
                            slot=f"local:{side.id}",
                            obligation="null.narrowed_by_guard",
                            confidence=CONFIDENCE_INFERRED_STRONG,
                            sources=[SOURCE_GUARD],
                            evidence_refs=[_ev(SOURCE_GUARD, line, guard="is_not_none"),
                            ],
                        ))
                    if isinstance(side, ast.Name) and _is_none_compare(tested, side.id):
                        out.append(_record(
                            contract_type=NULLABILITY_CONTRACT,
                            file=file,
                            qualname=qual,
                            slot=f"local:{side.id}",
                            obligation="null.checked_before_use",
                            confidence=CONFIDENCE_INFERRED_STRONG,
                            sources=[SOURCE_GUARD],
                            evidence_refs=[_ev(SOURCE_GUARD, line, guard="is_none_branch"),
                            ],
                        ))

        ff = next((f for f in module_facts.get("functions", []) if f.get("name") == fn_node.name), {})
        for var, state in (ff.get("nullability") or {}).items():
            if state == "definitely_not_none":
                out.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot=f"local:{var}",
                    obligation="null.forbidden",
                    confidence=CONFIDENCE_INFERRED_STRONG,
                    sources=[SOURCE_GUARD],
                    evidence_refs=[_ev(SOURCE_GUARD, ff.get("line", 0), fact_state=state),
                    ],
                ))
            elif state == "definitely_none":
                out.append(_record(
                    contract_type=NULLABILITY_CONTRACT,
                    file=file,
                    qualname=qual,
                    slot=f"local:{var}",
                    obligation="null.allowed",
                    confidence=CONFIDENCE_INFERRED_STRONG,
                    sources=[SOURCE_GUARD],
                    evidence_refs=[_ev(SOURCE_GUARD, ff.get("line", 0), fact_state=state),
                    ],
                ))

    return out


def _statistics(
    return_contracts: List[Dict],
    argument_contracts: List[Dict],
    nullability_contracts: List[Dict],
    exception_contracts: List[Dict],
    state_mutation_contracts: List[Dict],
) -> Dict[str, Any]:
    all_records = (
        return_contracts + argument_contracts + nullability_contracts
        + exception_contracts + state_mutation_contracts
    )
    by_kind: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    for rec in all_records:
        by_kind[rec["contract_type"]] = by_kind.get(rec["contract_type"], 0) + 1
        by_confidence[rec["confidence"]] = by_confidence.get(rec["confidence"], 0) + 1
        for src in rec.get("sources") or []:
            by_source[src] = by_source.get(src, 0) + 1
    return {
        "total": len(all_records),
        "by_kind": dict(sorted(by_kind.items())),
        "by_confidence": dict(sorted(by_confidence.items())),
        "by_source": dict(sorted(by_source.items())),
    }


def extract_module_contracts(
    module_facts: Dict[str, Any],
    tree: ast.AST,
    file: str,
) -> Dict[str, Any]:
    """Extract all contract facts for one module. Findings-free."""
    if module_facts.get("parse_error"):
        return {"enabled": True, "parse_error": module_facts["parse_error"]}

    ret_hint, arg_hint, null_hint = _extract_type_hints(tree, file)
    ret_doc, arg_doc, exc_doc = _extract_docstrings(tree, file)
    _, arg_assert, null_assert, state_assert = _extract_asserts(tree, file)
    ret_test = _extract_tests(module_facts, file)
    ret_caller = _extract_caller_behavior(module_facts.get("interproc"), file)
    arg_callee, null_callee = _extract_callee_behavior(tree, file)
    null_guard = _extract_guards(module_facts, tree, file)
    state_init = _extract_state_init(tree, file)

    return_contracts = ret_hint + ret_doc + ret_test + ret_caller
    argument_contracts = arg_hint + arg_doc + arg_assert + arg_callee
    nullability_contracts = null_hint + null_assert + null_callee + null_guard
    exception_contracts = exc_doc
    state_mutation_contracts = state_assert + state_init

    return {
        "enabled": True,
        "return_contracts": return_contracts,
        "argument_contracts": argument_contracts,
        "nullability_contracts": nullability_contracts,
        "exception_contracts": exception_contracts,
        "state_mutation_contracts": state_mutation_contracts,
        "statistics": _statistics(
            return_contracts,
            argument_contracts,
            nullability_contracts,
            exception_contracts,
            state_mutation_contracts,
        ),
    }
