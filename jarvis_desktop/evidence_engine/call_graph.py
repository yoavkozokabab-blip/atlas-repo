"""Function-level call graph from AST scans and optional depgraph edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .symbol_index import SymbolIndex


@dataclass
class CallGraph:
    callers: Dict[str, Set[str]] = field(default_factory=dict)  # callee -> callers (file::qual)
    callees: Dict[str, Set[str]] = field(default_factory=dict)  # caller -> callees
    file_calls: Dict[str, List[Tuple[str, str, int]]] = field(default_factory=dict)

    def add_call(self, caller_file: str, caller_qual: str, callee: str, line: int) -> None:
        caller_key = f"{caller_file}::{caller_qual or '<module>'}"
        callee_key = callee
        self.callers.setdefault(callee_key, set()).add(caller_key)
        self.callees.setdefault(caller_key, set()).add(callee_key)
        self.file_calls.setdefault(caller_file, []).append((caller_qual, callee, line))

    def who_calls(self, symbol: str) -> List[str]:
        return sorted(self.callers.get(symbol, set()))

    def who_depends_on_file(self, file_path: str) -> List[str]:
        deps: Set[str] = set()
        prefix = file_path.replace("\\", "/")
        for caller, callees in self.callees.items():
            if caller.startswith(prefix + "::"):
                deps.update(callees)
        return sorted(deps)

    def data_entry_files(self, index: SymbolIndex) -> List[str]:
        """Files with middleware, handlers, or public API entry symbols."""
        patterns = ("middleware", "handler", "route", "endpoint", "controller", "api")
        scores: Dict[str, int] = {}
        for path, scan in index.files.items():
            score = 0
            for sym in scan.symbols:
                blob = (sym.name + " " + sym.qualname).lower()
                if any(p in blob for p in patterns):
                    score += 2
                if sym.kind in ("middleware", "function") and sym.decorators:
                    score += 1
            if score:
                scores[path] = score
        return [p for p, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:10]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "callers": {k: sorted(v) for k, v in self.callers.items()},
            "callees": {k: sorted(v) for k, v in self.callees.items()},
            "file_calls": {
                k: [{"caller": c[0], "callee": c[1], "line": c[2]} for c in v]
                for k, v in self.file_calls.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "CallGraph":
        g = cls()
        for callee, callers in (raw.get("callers") or {}).items():
            g.callers[callee] = set(callers)
        for caller, callees in (raw.get("callees") or {}).items():
            g.callees[caller] = set(callees)
        for path, calls in (raw.get("file_calls") or {}).items():
            g.file_calls[path] = [(c["caller"], c["callee"], c["line"]) for c in calls]
        return g


def build_call_graph(index: SymbolIndex, graph: Optional[Dict[str, Any]] = None) -> CallGraph:
    cg = CallGraph()
    for path, scan in index.files.items():
        for caller_qual, callee, line in scan.calls:
            cg.add_call(path, caller_qual, callee, line)

    if graph:
        for edge in graph.get("edges") or []:
            if edge.get("type") != "calls":
                continue
            src = edge.get("from") or ""
            dst = edge.get("to") or ""
            if "::" in src and "::" in dst:
                src_file = src.split("::", 1)[0].replace("module:", "")
                src_sym = src.split("::", 1)[1]
                dst_sym = dst.split("::", 1)[1] if "::" in dst else dst
                cg.add_call(src_file, src_sym, dst_sym, 0)
    return cg
