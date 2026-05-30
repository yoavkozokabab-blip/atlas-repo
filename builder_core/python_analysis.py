"""Deterministic Python AST analysis for Builder Core.

The analyzer is intentionally conservative. It reports review leads with
line-numbered evidence; it never edits source files and never claims proof of
correctness.
"""

from __future__ import annotations

import ast
import os
from typing import Any, Dict, Iterable, List

from . import semantic_reasoning

SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
_MUTATING_METHODS = {
    "add", "append", "clear", "discard", "extend", "insert", "pop",
    "remove", "reverse", "sort", "update",
}


def _line(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:240]
    return ""


def _finding(
    rule: str,
    severity: str,
    lineno: int,
    message: str,
    lines: List[str],
) -> Dict[str, Any]:
    return {
        "rule": rule,
        "severity": severity,
        "line": lineno,
        "message": message,
        "evidence": _line(lines, lineno),
    }


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _has_len_plus_one(node: ast.AST) -> bool:
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
        return False
    pieces = (node.left, node.right)
    has_one = any(isinstance(piece, ast.Constant) and piece.value == 1 for piece in pieces)
    has_len = any(
        isinstance(piece, ast.Call)
        and isinstance(piece.func, ast.Name)
        and piece.func.id == "len"
        for piece in pieces
    )
    return has_one and has_len


def _return_shape(node: ast.Return) -> str:
    value = node.value
    if value is None:
        return "none"
    if isinstance(value, ast.Constant):
        if isinstance(value.value, bool):
            return "bool"
        if value.value is None:
            return "none"
        return type(value.value).__name__
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Tuple):
        return "tuple"
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.Set):
        return "set"
    return "value"


def _walk_statement_lists(node: ast.AST) -> Iterable[List[ast.stmt]]:
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list) and value and all(isinstance(item, ast.stmt) for item in value):
            yield value
            for item in value:
                yield from _walk_statement_lists(item)
        elif isinstance(value, ast.AST):
            yield from _walk_statement_lists(value)


def _unreachable_findings(tree: ast.AST, lines: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for body in _walk_statement_lists(tree):
        terminated = False
        for statement in body:
            if terminated:
                findings.append(
                    _finding(
                        "unreachable_code",
                        "medium",
                        statement.lineno,
                        "Statement appears after an unconditional control-flow exit.",
                        lines,
                    )
                )
                break
            if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminated = True
    return findings


def _test_reference(path: str, test_documents: List[Dict[str, str]]) -> bool:
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return any(
        stem in document.get("path", "").lower()
        or stem in document.get("text", "").lower()
        for document in test_documents
    )


def analyze_python(
    path: str,
    text: str,
    *,
    test_documents: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Analyze one Python source file and return JSON-serializable signals."""
    lines = text.splitlines()
    findings: List[Dict[str, Any]] = []
    functions: List[Dict[str, Any]] = []
    referenced_by_tests = _test_reference(path, test_documents or [])

    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        lineno = int(exc.lineno or 1)
        return {
            "path": path,
            "parse_error": type(exc).__name__,
            "functions": [],
            "complexity": {"branches": 0, "loops": 0, "functions": 0},
            "referenced_by_tests": referenced_by_tests,
            "algorithm_profiles": [],
            "test_expectations": [],
            "findings": [
                _finding(
                    "syntax_error",
                    "high",
                    lineno,
                    "Python parser rejected this file.",
                    lines,
                )
            ],
        }

    branches = sum(isinstance(node, (ast.If, ast.IfExp, ast.Try, ast.Match)) for node in ast.walk(tree))
    loops = sum(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in ast.walk(tree))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_nodes = list(ast.walk(node))
            fn_branches = sum(isinstance(item, (ast.If, ast.IfExp, ast.Try, ast.Match)) for item in fn_nodes)
            fn_loops = sum(isinstance(item, (ast.For, ast.AsyncFor, ast.While)) for item in fn_nodes)
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "complexity": 1 + fn_branches + fn_loops,
                }
            )

            assigned = {
                item.id
                for item in fn_nodes
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
            }
            loaded = {
                item.id
                for item in fn_nodes
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
            }
            for name in sorted(assigned - loaded):
                if not name.startswith("_"):
                    findings.append(
                        _finding(
                            "unused_variable",
                            "low",
                            node.lineno,
                            f"Function '{node.name}' assigns '{name}' but never reads it.",
                            lines,
                        )
                    )

            recursive = any(
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == node.name
                for item in fn_nodes
            )
            conditional_return = any(
                isinstance(item, ast.If)
                and any(isinstance(child, ast.Return) for child in ast.walk(item))
                for item in fn_nodes
            )
            if recursive and not conditional_return:
                findings.append(
                    _finding(
                        "recursive_base_case",
                        "high",
                        node.lineno,
                        f"Recursive function '{node.name}' has no obvious conditional base-case return.",
                        lines,
                    )
                )

            return_shapes = {
                _return_shape(item) for item in fn_nodes if isinstance(item, ast.Return)
            }
            if len(return_shapes) > 1:
                findings.append(
                    _finding(
                        "wrong_return_shape",
                        "medium",
                        node.lineno,
                        f"Function '{node.name}' returns inconsistent shapes: {', '.join(sorted(return_shapes))}.",
                        lines,
                    )
                )

            lowered_name = node.name.lower()
            fn_text = "\n".join(lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)])
            has_queue_growth = ".extend(" in fn_text or ".append(" in fn_text
            has_graph_words = any(word in fn_text.lower() for word in ("successor", "neighbor", "adjacent"))
            has_membership_filter = any(
                isinstance(item, ast.Compare)
                and any(isinstance(op, (ast.In, ast.NotIn)) for op in item.ops)
                for item in fn_nodes
            )
            if (
                ("breadth_first" in lowered_name or lowered_name in {"bfs", "breadth_first_search"})
                and has_queue_growth
                and has_graph_words
                and not has_membership_filter
            ):
                findings.append(
                    _finding(
                        "algorithmic_mismatch",
                        "high",
                        node.lineno,
                        "Breadth-first search grows its queue without an obvious visited-membership filter; cycles may repeat forever.",
                        lines,
                    )
                )

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            if isinstance(node.test, ast.Constant) and node.test.value in (True, False):
                severity = "medium" if isinstance(node, ast.If) else "high"
                findings.append(
                    _finding(
                        "suspicious_conditional",
                        severity,
                        node.lineno,
                        f"{type(node).__name__.lower()} condition is constant {node.test.value!r}.",
                        lines,
                    )
                )
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if len(operands) == 2 and ast.dump(operands[0]) == ast.dump(operands[1]):
                findings.append(
                    _finding(
                        "suspicious_conditional",
                        "medium",
                        node.lineno,
                        "Comparison uses the same expression on both sides.",
                        lines,
                    )
                )
            if any(isinstance(op, (ast.LtE, ast.GtE)) for op in node.ops) and any(
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == "len"
                for item in operands
            ):
                findings.append(
                    _finding(
                        "off_by_one_risk",
                        "medium",
                        node.lineno,
                        "Inclusive comparison against len(...) may cross a sequence boundary.",
                        lines,
                    )
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            if any(_has_len_plus_one(arg) for arg in node.args):
                findings.append(
                    _finding(
                        "off_by_one_risk",
                        "high",
                        node.lineno,
                        "range(len(...) + 1) can produce an out-of-range index.",
                        lines,
                    )
                )
        if isinstance(node, (ast.For, ast.AsyncFor)):
            iter_name = _name(node.iter)
            if iter_name:
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and _name(child.func.value) == iter_name
                        and child.func.attr in _MUTATING_METHODS
                    ):
                        findings.append(
                            _finding(
                                "mutation_while_iterating",
                                "high",
                                child.lineno,
                                f"Loop mutates '{iter_name}' via {child.func.attr}() while iterating it.",
                                lines,
                            )
                        )
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            if not any(isinstance(child, (ast.Break, ast.Return, ast.Raise)) for child in ast.walk(node)):
                findings.append(
                    _finding(
                        "possible_infinite_loop",
                        "high",
                        node.lineno,
                        "while True loop has no obvious break, return, or raise path.",
                        lines,
                    )
                )

    findings.extend(_unreachable_findings(tree, lines))
    semantic = semantic_reasoning.analyze_semantics(
        tree,
        path,
        text,
        test_documents=list(test_documents or []),
    )
    findings.extend(semantic["findings"])
    if not referenced_by_tests:
        findings.append(
            _finding(
                "missing_test_reference",
                "low",
                1,
                "No indexed test file appears to reference this source module.",
                lines,
            )
        )

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for finding in findings:
        key = (finding["rule"], finding["line"], finding["message"])
        if key not in seen:
            deduped.append(finding)
            seen.add(key)
    deduped.sort(
        key=lambda item: (-SEVERITY_WEIGHT.get(item["severity"], 0), item["line"], item["rule"])
    )

    return {
        "path": path,
        "parse_error": "",
        "functions": functions,
        "complexity": {
            "branches": branches,
            "loops": loops,
            "functions": len(functions),
        },
        "referenced_by_tests": referenced_by_tests,
        "algorithm_profiles": semantic["profiles"],
        "test_expectations": semantic["test_expectations"],
        "findings": deduped,
    }
