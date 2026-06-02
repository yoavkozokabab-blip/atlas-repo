"""Conservative callable export index for project modules.

Indexes only callable targets that are explicit in the source tree:
- module-level functions;
- module-level classes with an explicit ``__init__`` method, targeting that
  concrete constructor method; and
- explicit, unambiguous imports in package ``__init__.py`` files.

No star imports, runtime assignments, implicit package exports, inherited
constructors, or ambiguous bindings are resolved.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, Iterable, Tuple

from . import imports

FunctionId = Tuple[str, str]


def _file_package(rel_path: str) -> str:
    return ".".join(rel_path.split("/")[:-1])


def _add_export(
    exports: Dict[str, Dict[str, FunctionId]],
    ambiguous: Dict[str, set[str]],
    module: str,
    name: str,
    target: FunctionId,
) -> bool:
    if name in ambiguous.setdefault(module, set()):
        return False
    current = exports.setdefault(module, {}).get(name)
    if current is None:
        exports[module][name] = target
        return True
    if current != target:
        ambiguous[module].add(name)
        exports[module].pop(name, None)
    return False


def build_export_index(
    parsed: Iterable[Tuple[str, ast.AST]],
    module_map: Dict[str, Any],
) -> Dict[str, Any]:
    """Return explicit callable exports keyed by dotted project module."""
    parsed_list = list(parsed)
    exports: Dict[str, Dict[str, FunctionId]] = {}
    ambiguous: Dict[str, set[str]] = {}
    package_reexports: list[Tuple[str, str, str, str]] = []

    for rel, tree in parsed_list:
        module = module_map["path_to_module"].get(rel)
        if module is None:
            continue
        for child in getattr(tree, "body", []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _add_export(exports, ambiguous, module, child.name, (rel, child.name))
            elif isinstance(child, ast.ClassDef):
                explicit_init = next(
                    (
                        item
                        for item in child.body
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == "__init__"
                    ),
                    None,
                )
                if explicit_init is not None:
                    _add_export(
                        exports,
                        ambiguous,
                        module,
                        child.name,
                        (rel, f"{child.name}.__init__"),
                    )

        if not rel.endswith("__init__.py"):
            continue
        table = imports.build_import_table(tree, _file_package(rel))
        for local, (source_module, source_name) in sorted(table["direct"].items()):
            if local in table["ambiguous"]:
                ambiguous.setdefault(module, set()).add(local)
                exports.setdefault(module, {}).pop(local, None)
                continue
            package_reexports.append((module, local, source_module, source_name))

    # Explicit package re-exports may form short chains. Iterate to a fixpoint;
    # unresolved or cyclic chains remain absent rather than being guessed.
    changed = True
    while changed:
        changed = False
        for module, local, source_module, source_name in package_reexports:
            if source_module not in module_map["module_to_path"]:
                continue
            target = exports.get(source_module, {}).get(source_name)
            if target is None:
                continue
            if _add_export(exports, ambiguous, module, local, target):
                changed = True

    return {
        "exports": {
            module: dict(sorted(symbols.items()))
            for module, symbols in sorted(exports.items())
        },
        "ambiguous": {
            module: sorted(names)
            for module, names in sorted(ambiguous.items())
            if names
        },
    }

