"""Python AST scanner for symbol definitions, imports, calls, and inheritance."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .evidence_models import SymbolKind, SymbolRecord


@dataclass
class FileScanResult:
    path: str
    symbols: List[SymbolRecord] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    calls: List[Tuple[str, str, int]] = field(default_factory=list)  # caller_qual, callee, line
    parse_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": list(self.imports),
            "calls": [{"caller": c[0], "callee": c[1], "line": c[2]} for c in self.calls],
            "parse_error": self.parse_error,
        }


def _decorator_names(node: ast.AST) -> List[str]:
    decs = getattr(node, "decorator_list", None) or []
    out: List[str] = []
    for dec in decs:
        if isinstance(dec, ast.Name):
            out.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            out.append(dec.attr)
        elif isinstance(dec, ast.Call):
            fn = dec.func
            if isinstance(fn, ast.Name):
                out.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                out.append(fn.attr)
    return out


def _base_names(node: ast.ClassDef) -> List[str]:
    bases: List[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
    return bases


def _classify_kind(node: ast.AST, name: str, decorators: List[str]) -> str:
    dec_lower = {d.lower() for d in decorators}
    if any(d in dec_lower for d in ("abstractmethod", "abstractclassmethod")):
        return SymbolKind.ABSTRACT.value
    if isinstance(node, ast.ClassDef):
        if any(b in ("Protocol", "ABC") for b in _base_names(node)):
            return SymbolKind.PROTOCOL.value
        if "register" in name.lower() or "registry" in name.lower():
            return SymbolKind.REGISTRY.value
        if "middleware" in name.lower() or "Middleware" in _base_names(node):
            return SymbolKind.MIDDLEWARE.value
        if "Factory" in name or name.endswith("Factory"):
            return SymbolKind.FACTORY.value
        return SymbolKind.CLASS.value
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        parent = getattr(node, "_parent_class", None)
        if parent:
            return SymbolKind.METHOD.value
        if "middleware" in name.lower():
            return SymbolKind.MIDDLEWARE.value
        return SymbolKind.FUNCTION.value
    return SymbolKind.FUNCTION.value


class _ScanVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.symbols: List[SymbolRecord] = []
        self.imports: List[str] = []
        self.calls: List[Tuple[str, str, int]] = []
        self._class_stack: List[str] = []
        self._func_stack: List[str] = []

    @property
    def _current_qual(self) -> str:
        parts = self._class_stack + self._func_stack
        return ".".join(parts) if parts else ""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
            self.symbols.append(
                SymbolRecord(
                    name=alias.asname or alias.name.split(".")[-1],
                    kind=SymbolKind.IMPORT.value,
                    file_path=self.path,
                    line=node.lineno,
                    qualname=alias.name,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            full = f"{module}.{alias.name}" if module else alias.name
            self.imports.append(full)
            self.symbols.append(
                SymbolRecord(
                    name=alias.asname or alias.name,
                    kind=SymbolKind.IMPORT.value,
                    file_path=self.path,
                    line=node.lineno,
                    qualname=full,
                )
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        decorators = _decorator_names(node)
        kind = _classify_kind(node, node.name, decorators)
        qual = ".".join(self._class_stack + [node.name]) if self._class_stack else node.name
        self.symbols.append(
            SymbolRecord(
                name=node.name,
                kind=kind,
                file_path=self.path,
                line=node.lineno,
                qualname=qual,
                decorators=decorators,
                bases=_base_names(node),
            )
        )
        self._class_stack.append(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                setattr(child, "_parent_class", node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        name = getattr(node, "name", "")
        decorators = _decorator_names(node)
        kind = _classify_kind(node, name, decorators)
        if self._class_stack:
            qual = ".".join(self._class_stack + [name])
        else:
            qual = name
        self.symbols.append(
            SymbolRecord(
                name=name,
                kind=kind,
                file_path=self.path,
                line=getattr(node, "lineno", 0),
                qualname=qual,
                decorators=decorators,
            )
        )
        self._func_stack.append(name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callee = ""
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr
        if callee:
            self.calls.append((self._current_qual, callee, node.lineno))
        self.generic_visit(node)


def scan_python_source(path: str, source: str) -> FileScanResult:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return FileScanResult(path=path, parse_error=str(exc))

    visitor = _ScanVisitor(path)
    visitor.visit(tree)

    # Detect config-style assignments (feature flags, settings)
    for match in re.finditer(
        r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*",
        source,
        re.MULTILINE,
    ):
        name = match.group(1)
        if any(k in name.lower() for k in ("feature", "flag", "config", "setting", "slippage", "fill", "broker", "backtest", "paper")):
            visitor.symbols.append(
                SymbolRecord(
                    name=name,
                    kind=SymbolKind.CONFIG.value,
                    file_path=path,
                    line=source[: match.start()].count("\n") + 1,
                    qualname=name,
                )
            )

    return FileScanResult(
        path=path,
        symbols=visitor.symbols,
        imports=visitor.imports,
        calls=visitor.calls,
    )


def scan_python_file(abs_path: str, rel_path: str) -> FileScanResult:
    try:
        text = open(abs_path, "r", encoding="utf-8-sig", errors="ignore").read()
    except OSError as exc:
        return FileScanResult(path=rel_path, parse_error=str(exc))
    result = scan_python_source(rel_path, text)
    result.path = rel_path.replace("\\", "/")
    return result
