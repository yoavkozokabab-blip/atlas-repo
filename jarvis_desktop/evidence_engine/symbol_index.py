"""Repository-wide symbol index built from AST scans."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .ast_scanner import FileScanResult, scan_python_file
from .evidence_models import SymbolRecord


@dataclass
class SymbolIndex:
    project_root: str
    files: Dict[str, FileScanResult] = field(default_factory=dict)
    by_name: Dict[str, List[SymbolRecord]] = field(default_factory=dict)
    by_kind: Dict[str, List[SymbolRecord]] = field(default_factory=dict)
    parse_errors: Dict[str, str] = field(default_factory=dict)

    def remove_file(self, path: str) -> None:
        """Drop a file and its symbols from the index (targeted refresh)."""
        path = path.replace("\\", "/")
        scan = self.files.pop(path, None)
        self.parse_errors.pop(path, None)
        if not scan:
            return
        for sym in scan.symbols:
            key = sym.name.lower()
            if key in self.by_name:
                self.by_name[key] = [r for r in self.by_name[key] if r.file_path != path]
                if not self.by_name[key]:
                    del self.by_name[key]
            if sym.kind in self.by_kind:
                self.by_kind[sym.kind] = [r for r in self.by_kind[sym.kind] if r.file_path != path]
                if not self.by_kind[sym.kind]:
                    del self.by_kind[sym.kind]

    def add_scan(self, scan: FileScanResult) -> None:
        path = scan.path.replace("\\", "/")
        self.remove_file(path)
        self.files[path] = scan
        if scan.parse_error:
            self.parse_errors[path] = scan.parse_error
            return
        for sym in scan.symbols:
            key = sym.name.lower()
            self.by_name.setdefault(key, []).append(sym)
            self.by_kind.setdefault(sym.kind, []).append(sym)

    def symbols_in_file(self, path: str) -> List[SymbolRecord]:
        scan = self.files.get(path.replace("\\", "/"))
        return list(scan.symbols) if scan else []

    def find_names(self, patterns: Iterable[str]) -> List[SymbolRecord]:
        pats = [p.lower() for p in patterns if p]
        hits: List[SymbolRecord] = []
        seen: Set[Tuple[str, str, int]] = set()
        for name, records in self.by_name.items():
            for pat in pats:
                if pat in name or name in pat:
                    for rec in records:
                        key = (rec.file_path, rec.qualname or rec.name, rec.line)
                        if key not in seen:
                            seen.add(key)
                            hits.append(rec)
        return hits

    def find_in_source(self, patterns: Iterable[str]) -> List[SymbolRecord]:
        """Match symbol names, qualnames, imports, and decorators."""
        pats = [p.lower() for p in patterns if p]
        hits: List[SymbolRecord] = []
        seen: Set[Tuple[str, str]] = set()
        for scan in self.files.values():
            for sym in scan.symbols:
                blob = " ".join(
                    [
                        sym.name,
                        sym.qualname,
                        " ".join(sym.decorators),
                        " ".join(sym.bases),
                        " ".join(scan.imports),
                    ]
                ).lower()
                if any(p in blob for p in pats):
                    key = (sym.file_path, sym.qualname or sym.name)
                    if key not in seen:
                        seen.add(key)
                        hits.append(sym)
        return hits

    def find_by_kind(self, kind: str) -> List[SymbolRecord]:
        return list(self.by_kind.get(kind, []))

    def files_with_pattern(self, patterns: Iterable[str]) -> List[str]:
        pats = [p.lower() for p in patterns if p]
        out: List[str] = []
        for path, scan in self.files.items():
            blob = path.lower()
            for sym in scan.symbols:
                blob += " " + sym.name.lower() + " " + (sym.qualname or "").lower()
            if any(p in blob for p in pats):
                out.append(path)
        return sorted(set(out))

    def usage_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for scan in self.files.values():
            for _caller, callee, _line in scan.calls:
                counts[callee] = counts.get(callee, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_root": self.project_root,
            "file_count": len(self.files),
            "symbol_count": sum(len(s.symbols) for s in self.files.values()),
            "parse_errors": dict(self.parse_errors),
            "files": {p: s.to_dict() for p, s in self.files.items()},
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SymbolIndex":
        idx = cls(project_root=raw.get("project_root") or "")
        idx.parse_errors = dict(raw.get("parse_errors") or {})
        for path, fdata in (raw.get("files") or {}).items():
            symbols = [SymbolRecord(**s) for s in (fdata.get("symbols") or [])]
            calls = [(c["caller"], c["callee"], c["line"]) for c in (fdata.get("calls") or [])]
            scan = FileScanResult(
                path=path,
                symbols=symbols,
                imports=list(fdata.get("imports") or []),
                calls=calls,
                parse_error=fdata.get("parse_error"),
            )
            idx.add_scan(scan)
        return idx


def build_symbol_index(
    project_root: str,
    module_paths: Iterable[str],
    *,
    max_files: int = 800,
) -> SymbolIndex:
    root = os.path.abspath(project_root)
    index = SymbolIndex(project_root=root)
    count = 0
    for rel in module_paths:
        if count >= max_files:
            break
        rel_posix = rel.replace("\\", "/")
        if not rel_posix.endswith(".py"):
            continue
        abs_path = os.path.join(root, rel_posix)
        if not os.path.isfile(abs_path):
            continue
        index.add_scan(scan_python_file(abs_path, rel_posix))
        count += 1
    usages = index.usage_counts()
    for records in index.by_name.values():
        for rec in records:
            rec.usage_count = usages.get(rec.name, 0) + usages.get(rec.qualname.split(".")[-1], 0)
    return index
