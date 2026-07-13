"""Deterministic repository structure summaries for Builder Core.

RU-2 deliberately stays structural: path roles, top-level subsystems, entry
files, and Python import dependencies. It does not infer behavior or feed bug
detectors.
"""

from __future__ import annotations

import ast
import os
from collections import Counter
from typing import Any, Dict, Iterable, List

FILE_ROLES = {
    "production_code",
    "test",
    "benchmark",
    "dataset",
    "generated",
    "report_history",
    "architecture_doc",
    "general_doc",
    "config",
    "unknown",
}

_CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift", ".scala",
    ".php", ".sh", ".ps1", ".lua", ".m", ".mm",
}
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
_CONFIG_EXTS = {".toml", ".yaml", ".yml", ".ini", ".cfg"}
_CONFIG_NAMES = {
    ".editorconfig",
    ".env.example",
    "dockerfile",
    "makefile",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "tox.ini",
    "tsconfig.json",
}
_BENCHMARK_PARTS = {
    "benchmark",
    "benchmarks",
    "bugsinpy",
    "external_benchmarks",
    "holdout",
    "quixbugs",
}
_DATASET_PARTS = {
    "data", "dataset", "datasets", "fixtures", "samples", "testdata", "test_data",
}
_DOCUMENTATION_CODE_PARTS = {
    "doc", "docs", "docs_src", "documentation", "example", "examples",
    "tutorial", "tutorials",
}
_GENERATED_PARTS = {
    ".cache", ".mypy_cache", ".next", ".pytest_cache", ".pytest_tmp", "__pycache__",
    "backups", "build", "coverage", "dist", "generated", "htmlcov", "node_modules",
    "site-packages", "target", "tests_tmp", "vendor", "generated_snippets",
}
_GENERATED_DIR_PREFIXES = (
    ".checkpoint_", ".design_runtime", ".home_checkpoint_", ".manual_py_temp",
    ".phase", ".pytest_", ".redesign_", "atlaspytesttemp", "pytest_",
)
_GENERATED_PATH_PREFIXES = (
    "packaging/installer/output/",
    "packaging/installer/staging/",
)
_TEST_PARTS = {"__tests__", "spec", "test", "tests"}
_ENTRY_NAMES = (
    "main.py",
    "app.py",
    "cli.py",
    "router.py",
    "runtime.py",
    "engine.py",
    "voice_loop.py",
    "wakeword.py",
    "__init__.py",
)
_ROLE_PRIORITY = {
    "production_code": 0,
    "architecture_doc": 1,
    "config": 2,
    "test": 3,
    "general_doc": 4,
    "report_history": 5,
    "benchmark": 6,
    "dataset": 7,
    "generated": 8,
    "unknown": 9,
}


def _parts(rel_path: str) -> List[str]:
    return rel_path.replace("\\", "/").lower().split("/")


def is_generated_runtime_path(rel_path: str, *, is_dir: bool = False) -> bool:
    """Identify Atlas/packager/test outputs that are never first-party source."""
    normalized = rel_path.replace("\\", "/").lower().strip("/")
    parts = normalized.split("/") if normalized else []
    if any(part in _GENERATED_PARTS for part in parts):
        return True
    if any(part.startswith(_GENERATED_DIR_PREFIXES) for part in parts):
        return True
    candidate = normalized + ("/" if is_dir and normalized else "")
    return any(candidate.startswith(prefix) for prefix in _GENERATED_PATH_PREFIXES)


def classify_file_role(
    rel_path: str, ext: str | None = None, *, project_root: str | None = None
) -> str:
    """Assign one stable role from path and extension only."""
    parts = _parts(rel_path)
    name = parts[-1]
    stem, inferred_ext = os.path.splitext(name)
    ext = (ext or inferred_ext).lower()
    dirs = set(parts[:-1])
    root_name = os.path.basename(os.path.abspath(project_root or "")).lower()

    if is_generated_runtime_path(rel_path) or name.endswith((".pyc", ".min.js", ".min.css")):
        return "generated"
    if (
        dirs & _BENCHMARK_PARTS
        or "bugsinpy" in rel_path.lower()
        or "quixbugs" in rel_path.lower()
        or (
            root_name == "quixbugs"
            and bool(dirs & {"python_programs", "correct_python_programs"})
        )
    ):
        return "benchmark"
    if "reports" in dirs:
        return "report_history"
    if ext in _CODE_EXTS and dirs & _DOCUMENTATION_CODE_PARTS:
        return "general_doc"
    if ext in _CODE_EXTS and dirs & _DATASET_PARTS:
        return "dataset"
    if dirs & _DATASET_PARTS and ext in {".csv", ".json", ".jsonl", ".tsv", ".txt"}:
        return "dataset"
    if name == "readme_architecture.md" or (
        ext in _DOC_EXTS
        and any(token in stem for token in ("architecture", "design", "overview"))
    ):
        return "architecture_doc"
    if (
        name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
        or dirs & _TEST_PARTS
    ) and ext in _CODE_EXTS:
        return "test"
    if name in _CONFIG_NAMES or ext in _CONFIG_EXTS:
        return "config"
    if ext in _CODE_EXTS:
        return "production_code"
    if ext in _DOC_EXTS:
        return "general_doc"
    return "unknown"


def legacy_category(role: str, rel_path: str) -> str | None:
    """Preserve the Phase 82 category contract for existing risk consumers."""
    if role == "test":
        return "test"
    if role == "production_code":
        return "src"
    if role in {"architecture_doc", "general_doc", "report_history"}:
        return "readme" if os.path.basename(rel_path).lower().startswith("readme") else "docs"
    if role == "config":
        return "config"
    if role in {"benchmark", "dataset"}:
        return "benchmark"
    return None


def is_indexable(rel_path: str, ext: str, *, project_root: str | None = None) -> bool:
    role = classify_file_role(rel_path, ext, project_root=project_root)
    return role != "unknown" and (
        ext in _CODE_EXTS
        or ext in _DOC_EXTS
        or ext in _CONFIG_EXTS
        or os.path.basename(rel_path).lower() in _CONFIG_NAMES
    )


def _subsystem_name(rel_path: str) -> str:
    """Stable subsystem key — deeper grouping for large Python monorepos."""
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return "(root)"
    # homeassistant/components/<domain>/... -> per-integration subsystem
    if len(parts) >= 3 and parts[0] == "homeassistant" and parts[1] == "components":
        return "/".join(parts[:3])
    # homeassistant/<area>/... (auth, helpers, loader, ...)
    if len(parts) >= 2 and parts[0] == "homeassistant":
        return "/".join(parts[:2])
    # Generic src/pkg layout
    if len(parts) >= 3 and parts[0] in ("src", "lib", "app", "pkg"):
        return "/".join(parts[:3])
    if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "pkg"):
        return "/".join(parts[:2])
    return parts[0]


def _dominant_role(files: Iterable[Dict[str, Any]]) -> str:
    counts = Counter(str(item.get("role", "unknown")) for item in files)
    return min(counts, key=lambda role: (-counts[role], _ROLE_PRIORITY.get(role, 99), role))


def _entry_files(files: Iterable[Dict[str, Any]]) -> List[str]:
    production = sorted(
        item["path"] for item in files if item.get("role") == "production_code"
    )
    if not production:
        return []
    ranked = sorted(
        production,
        key=lambda path: (
            _ENTRY_NAMES.index(os.path.basename(path))
            if os.path.basename(path) in _ENTRY_NAMES else len(_ENTRY_NAMES),
            path.count("/"),
            path,
        ),
    )
    return ranked[:5]


def _imported_subsystems(text: str) -> List[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    names = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return sorted(names)


def discover_subsystems(
    files: List[Dict[str, Any]], python_documents: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """Create a stable top-level subsystem map from indexed files and imports."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in files:
        grouped.setdefault(_subsystem_name(item["path"]), []).append(item)

    names = set(grouped)
    dependencies: Dict[str, set[str]] = {name: set() for name in names}
    for document in python_documents:
        source_name = _subsystem_name(document["path"])
        for target_name in _imported_subsystems(document["text"]):
            if target_name in names and target_name != source_name:
                dependencies[source_name].add(target_name)

    subsystems = []
    for name in sorted(names):
        subsystem_files = grouped[name]
        role_counts = Counter(str(item.get("role", "unknown")) for item in subsystem_files)
        subsystems.append(
            {
                "name": name,
                "role": _dominant_role(subsystem_files),
                "file_count": len(subsystem_files),
                "entry_files": _entry_files(subsystem_files),
                "dependencies": sorted(dependencies[name]),
                "role_counts": dict(sorted(role_counts.items())),
            }
        )
    return subsystems


def production_subsystems(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return production-bearing subsystems in stable importance order."""
    subsystems = [
        item for item in index.get("subsystems", [])
        if item.get("role_counts", {}).get("production_code", 0) > 0
    ]
    return sorted(
        subsystems,
        key=lambda item: (
            -item.get("role_counts", {}).get("production_code", 0),
            -len(item.get("entry_files", [])),
            item.get("name", ""),
        ),
    )
