"""Per-file import table (Phase 93C — infrastructure).

Extracts only MODULE-LEVEL imports in their *safe* forms. The table is the sole
authority for cross-file resolution; anything not captured here stays UNRESOLVED.

Captured:
- ``from pkg.mod import func [as alias]``  -> direct[alias|func] = (pkg.mod, func)
- ``import pkg.mod [as m]``                -> handles[m|"pkg.mod"] = "pkg.mod"
- ``from .mod import func``                -> direct[func] = (<pkg>.mod, func)
- ``from . import mod``                    -> handles[mod] = (<pkg>.mod)

Flagged for UNRESOLVED:
- ``from m import *``      -> has_star (any non-direct bare name is ambiguous)
- a local name imported from two different targets -> ambiguous
Imports inside functions / try / conditionals are intentionally NOT collected
(dynamic/conditional), so calls relying on them remain UNRESOLVED.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, Optional


def _base_pkg_for_relative(file_package: str, level: int) -> Optional[str]:
    segs = file_package.split(".") if file_package else []
    drop = level - 1
    if drop > len(segs):
        return None  # too many dots to resolve -> caller treats as unresolved
    base = segs[: len(segs) - drop] if drop else segs
    return ".".join(base)


def build_import_table(tree: ast.AST, file_package: str) -> Dict[str, Any]:
    direct: Dict[str, tuple] = {}
    handles: Dict[str, str] = {}
    ambiguous: set = set()
    star_modules: list = []

    def add_direct(local: str, target: tuple) -> None:
        if local in direct and direct[local] != target:
            ambiguous.add(local)
        else:
            direct[local] = target

    for node in getattr(tree, "body", []):  # MODULE-LEVEL only
        try:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name  # e.g. "pkg.mod"
                    if alias.asname:
                        handles[alias.asname] = mod
                    else:
                        handles[mod] = mod  # `pkg.mod.func()` -> value dotted == "pkg.mod"
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                if level == 0:
                    base = node.module
                    if base is None:
                        continue
                else:
                    base_pkg = _base_pkg_for_relative(file_package, level)
                    if base_pkg is None:
                        continue
                    if node.module:
                        base = f"{base_pkg}.{node.module}" if base_pkg else node.module
                    else:
                        # from . import mod  -> module handles
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            sub = f"{base_pkg}.{alias.name}" if base_pkg else alias.name
                            handles[alias.asname or alias.name] = sub
                        continue
                for alias in node.names:
                    if alias.name == "*":
                        star_modules.append(base)
                        continue
                    add_direct(alias.asname or alias.name, (base, alias.name))
        except Exception:
            continue

    return {
        "direct": direct,
        "handles": handles,
        "ambiguous": ambiguous,
        "has_star": bool(star_modules),
        "star_modules": star_modules,
    }
