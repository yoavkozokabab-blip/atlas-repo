"""Filesystem layer for builder_core project memory.

The *only* place builder_core is permitted to write is
``<project>/.jarvis_builder/``. Everything else is read-only.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterator, List, Optional

from . import DECISIONS_FILENAME, INDEX_FILENAME, MEMORY_DIRNAME


def resolve_project_root(project: str) -> str:
    root = os.path.abspath(os.path.expanduser(project))
    if not os.path.isdir(root):
        raise ValueError(f"Project directory does not exist: {root}")
    return root


def memory_dir(project_root: str) -> str:
    return os.path.join(project_root, MEMORY_DIRNAME)


def index_path(project_root: str) -> str:
    return os.path.join(memory_dir(project_root), INDEX_FILENAME)


def decisions_path(project_root: str) -> str:
    return os.path.join(memory_dir(project_root), DECISIONS_FILENAME)


def ensure_memory_dir(project_root: str) -> str:
    path = memory_dir(project_root)
    if os.path.lexists(path) and os.path.islink(path):
        raise ValueError(".jarvis_builder must not be a symbolic link.")
    os.makedirs(path, exist_ok=True)
    project_real = os.path.realpath(project_root)
    memory_real = os.path.realpath(path)
    if os.path.commonpath([project_real, memory_real]) != project_real:
        raise ValueError(".jarvis_builder resolved outside the target project.")
    return path


def save_index(project_root: str, index: Dict[str, Any]) -> str:
    ensure_memory_dir(project_root)
    path = index_path(project_root)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    return path


def load_index(project_root: str) -> Optional[Dict[str, Any]]:
    path = index_path(project_root)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def append_decision(project_root: str, record: Dict[str, Any]) -> str:
    ensure_memory_dir(project_root)
    path = decisions_path(project_root)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def iter_decisions(project_root: str) -> Iterator[Dict[str, Any]]:
    path = decisions_path(project_root)
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_decisions(project_root: str) -> List[Dict[str, Any]]:
    return list(iter_decisions(project_root))
