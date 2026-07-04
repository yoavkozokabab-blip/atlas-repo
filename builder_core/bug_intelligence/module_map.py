"""Project module map (Phase 93C — infrastructure).

Maps repo-relative POSIX paths to dotted module paths. Handles the common
layouts:

  * flat:      ``pkg/mod.py``                      <-> ``pkg.mod``
  * src:       ``src/pkg/mod.py``                  <-> ``pkg.mod``
  * monorepo:  ``libs/core/pkg/mod.py``            <-> ``pkg.mod``

A *source root* is any directory that directly contains a top-level package
(a directory with ``__init__.py`` whose parent directory has none). Dotted
names are computed relative to the nearest source root, so absolute imports
(``from pkg import mod``) resolve regardless of where the package lives in the
repository. The repo root is always a source root (covers flat layouts and
loose top-level modules).

Any path segment that is not a valid identifier, or any dotted name that two
files would map to, is left out — making calls into it UNRESOLVED.
Conservative by design; ephemeral; never persisted.
"""

from __future__ import annotations

import keyword
from typing import Dict, Iterable, List, Set


def _is_identifier(seg: str) -> bool:
    return bool(seg) and seg.isidentifier() and not keyword.iskeyword(seg)


def path_to_dotted(rel_path: str) -> str | None:
    """Repo-root-relative dotted name (legacy behavior, kept for callers)."""
    if not rel_path.endswith(".py"):
        return None
    parts = rel_path[:-3].split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or any(not _is_identifier(seg) for seg in parts):
        return None
    return ".".join(parts)


def _source_roots(rel_paths: List[str]) -> List[str]:
    """Directories (as ``a/b`` prefixes; ``""`` = repo root) that contain
    top-level packages. A package dir is top-level when its parent dir has no
    ``__init__.py``."""
    files = set(rel_paths)
    pkg_dirs: Set[str] = set()
    for p in files:
        if p.endswith("/__init__.py"):
            pkg_dirs.add(p[: -len("/__init__.py")])
        elif p == "__init__.py":
            pkg_dirs.add("")
    roots: Set[str] = {""}
    for d in pkg_dirs:
        if not d:
            continue
        parent = d.rsplit("/", 1)[0] if "/" in d else ""
        if parent not in pkg_dirs:
            roots.add(parent)
    return sorted(roots, key=lambda r: -len(r))  # deepest root wins ties


def _dotted_under_root(rel_path: str, root: str) -> str | None:
    if root:
        prefix = root + "/"
        if not rel_path.startswith(prefix):
            return None
        sub = rel_path[len(prefix):]
    else:
        sub = rel_path
    return path_to_dotted(sub)


def build_module_map(rel_paths: Iterable[str]) -> Dict[str, Dict[str, str]]:
    paths = [p for p in rel_paths]
    roots = _source_roots(paths)
    path_to_module: Dict[str, str] = {}
    module_to_paths: Dict[str, list] = {}
    for p in paths:
        # Deepest matching source root gives the import-system dotted name.
        dotted = None
        for root in roots:
            dotted = _dotted_under_root(p, root)
            if dotted is not None:
                break
        if dotted is None:
            continue
        path_to_module[p] = dotted
        module_to_paths.setdefault(dotted, []).append(p)
        # Also register the repo-root-relative name when it differs, so legacy
        # callers that pass full-path dotted names (relative-import bases
        # computed from file paths) still resolve.
        legacy = path_to_dotted(p)
        if legacy and legacy != dotted:
            module_to_paths.setdefault(legacy, []).append(p)
            # NOTE: path_to_module keeps the import-system name (primary).
    # only keep modules that map to exactly one path (no ambiguity)
    module_to_path = {m: ps[0] for m, ps in module_to_paths.items() if len(ps) == 1}
    return {"path_to_module": path_to_module, "module_to_path": module_to_path}
