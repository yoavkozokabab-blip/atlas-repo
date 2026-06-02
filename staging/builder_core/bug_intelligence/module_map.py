"""Project module map (Phase 93C — infrastructure).

Maps repo-relative POSIX paths to dotted module paths for the common package
layout (``pkg/mod.py`` <-> ``pkg.mod``, ``pkg/__init__.py`` <-> ``pkg``). Any path
segment that is not a valid identifier, or any dotted name that two files would
map to, is left out — making calls into it UNRESOLVED. Conservative by design;
ephemeral; never persisted.
"""

from __future__ import annotations

import keyword
from typing import Dict, Iterable


def _is_identifier(seg: str) -> bool:
    return bool(seg) and seg.isidentifier() and not keyword.iskeyword(seg)


def path_to_dotted(rel_path: str) -> str | None:
    if not rel_path.endswith(".py"):
        return None
    parts = rel_path[:-3].split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or any(not _is_identifier(seg) for seg in parts):
        return None
    return ".".join(parts)


def build_module_map(rel_paths: Iterable[str]) -> Dict[str, Dict[str, str]]:
    path_to_module: Dict[str, str] = {}
    module_to_paths: Dict[str, list] = {}
    for p in rel_paths:
        dotted = path_to_dotted(p)
        if dotted is None:
            continue
        path_to_module[p] = dotted
        module_to_paths.setdefault(dotted, []).append(p)
    # only keep modules that map to exactly one path (no ambiguity)
    module_to_path = {m: ps[0] for m, ps in module_to_paths.items() if len(ps) == 1}
    return {"path_to_module": path_to_module, "module_to_path": module_to_path}
