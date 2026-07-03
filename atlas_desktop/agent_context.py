"""Derive agent-facing repository context from analysis + repo manifest files.

This enriches the canonical memory object (repository_memory). It is NOT a separate
memory store — it only derives fields that an AI coding agent needs (commands,
dependencies, conventions, structure, pitfalls) so Atlas can generate AGENTS.md /
CLAUDE.md as outputs. Everything is derived; nothing is manually maintained.
"""
from __future__ import annotations

import json
import os
import re
import ast
import configparser
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # Python 3.11+
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

_MAX_BYTES = 64 * 1024
_NOISE_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv", "env", "__pycache__",
    ".next", ".cache", "coverage", "htmlcov", ".idea", ".vscode", "target", "vendor",
    ".pytest_cache", ".mypy_cache", ".tox", "site-packages",
}
_UNKNOWN = "UNKNOWN"
_COMMAND_SLOTS = ("test", "build", "lint", "run")
_LANGUAGE_FAMILY_LABELS = {"python": "Python", "javascript": "JavaScript/Node"}
_WORKSPACE_DIRS = ("libs", "packages", "apps", "services")
_PY_MANIFESTS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "dev-requirements.txt",
    "tox.ini",
    "pytest.ini",
}
_JS_MANIFESTS = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
}


def _read(path: str, limit: int = _MAX_BYTES) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _has(repo: str, name: str) -> bool:
    return os.path.isfile(os.path.join(repo, name))


def _rel_parts(rel: str) -> List[str]:
    return [p for p in rel.replace("\\", "/").split("/") if p]


def _iter_repo_files(repo: str, *, max_files: int = 60000) -> Iterable[str]:
    """Yield repo-relative paths while ignoring generated/vendor directories."""
    seen = 0
    try:
        walker = os.walk(repo)
        for root, dirs, files in walker:
            dirs[:] = [
                d for d in dirs
                if d not in _NOISE_DIRS and not (d.startswith(".") and d not in {".github"})
            ]
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), repo).replace("\\", "/")
                parts = _rel_parts(rel)
                if any(p in _NOISE_DIRS for p in parts):
                    continue
                seen += 1
                if seen > max_files:
                    return
                yield rel
    except OSError:
        return


def _is_root_file(rel: str) -> bool:
    return "/" not in rel.replace("\\", "/")


def _is_test_path(rel: str) -> bool:
    parts = [p.lower() for p in _rel_parts(rel)]
    base = parts[-1] if parts else ""
    return (
        any(p in {"test", "tests", "testing", "js_tests", "spec", "specs", "t"} for p in parts[:-1])
        or base.startswith(("test_", "test."))
        or base.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def _score_manifest(rel: str, *, root: int, nested: int) -> int:
    if _is_root_file(rel):
        return root
    depth = len(_rel_parts(rel)) - 1
    if depth <= 3:
        return nested
    return max(3, nested // 3)


def _js_label(evidence: Dict[str, Any]) -> str:
    if evidence.get("typescript_files", 0) > 0 or any(
        str(p).endswith("tsconfig.json") for p in evidence.get("manifests", [])
    ):
        return "TypeScript"
    return "JavaScript/Node"


def _readme_summary(repo: str) -> str:
    for name in ("README.md", "README.rst", "README.txt", "readme.md", "Readme.md", "README"):
        p = os.path.join(repo, name)
        if os.path.isfile(p):
            txt = _read(p, 8192)
            body: List[str] = []
            seen_title = False
            for raw in txt.splitlines():
                line = raw.strip()
                if not line:
                    if body:
                        break
                    continue
                if line.startswith("#") and not seen_title:
                    seen_title = True
                    continue
                if line.startswith(("![", "[!", "<", "---", "===", ">", "|", "```")):
                    continue
                body.append(line)
                if len(" ".join(body)) > 260:
                    break
            return " ".join(body)[:300].strip()
    return ""


def detect_languages(repo: str) -> Dict[str, Any]:
    """Weighted language identity detection.

    Manifests are evidence, not identity. Source/test counts dominate so an
    auxiliary package.json cannot make a Python repository behave like JavaScript.
    """
    evidence: Dict[str, Dict[str, Any]] = {
        "python": {
            "source_files": 0,
            "test_files": 0,
            "manifest_files": 0,
            "lock_files": 0,
            "build_files": 0,
            "typescript_files": 0,
            "manifests": [],
            "score": 0,
        },
        "javascript": {
            "source_files": 0,
            "test_files": 0,
            "manifest_files": 0,
            "lock_files": 0,
            "build_files": 0,
            "typescript_files": 0,
            "manifests": [],
            "score": 0,
        },
    }

    for rel in _iter_repo_files(repo):
        lower = rel.lower()
        base = os.path.basename(lower)
        ext = os.path.splitext(lower)[1]

        if ext in {".py", ".pyi"}:
            ev = evidence["python"]
            ev["source_files"] += 1
            ev["score"] += 4
            if _is_test_path(rel):
                ev["test_files"] += 1
                ev["score"] += 1
        elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            if lower.endswith(".d.ts"):
                continue
            ev = evidence["javascript"]
            ev["source_files"] += 1
            ev["score"] += 3
            if ext in {".ts", ".tsx"}:
                ev["typescript_files"] += 1
            if _is_test_path(rel):
                ev["test_files"] += 1
                ev["score"] += 1

        if base in _PY_MANIFESTS or lower.startswith("requirements/"):
            ev = evidence["python"]
            ev["manifest_files"] += 1
            ev["manifests"].append(rel)
            ev["score"] += _score_manifest(rel, root=45, nested=16)
            if base in {"tox.ini", "pytest.ini"}:
                ev["build_files"] += 1
        elif base in _JS_MANIFESTS:
            ev = evidence["javascript"]
            ev["manifest_files"] += 1
            ev["manifests"].append(rel)
            if base in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
                ev["lock_files"] += 1
            ev["score"] += _score_manifest(rel, root=35, nested=12)
            if base == "tsconfig.json":
                ev["build_files"] += 1
        elif base in {"gruntfile.js", "gulpfile.js", "vite.config.js", "vite.config.ts"}:
            ev = evidence["javascript"]
            ev["build_files"] += 1
            ev["score"] += _score_manifest(rel, root=15, nested=6)
        elif base in {"noxfile.py", "conftest.py"}:
            ev = evidence["python"]
            ev["build_files"] += 1
            ev["score"] += _score_manifest(rel, root=10, nested=4)

    ranked = sorted(evidence.items(), key=lambda item: item[1]["score"], reverse=True)
    primary_family = ranked[0][0] if ranked and ranked[0][1]["score"] >= 20 else ""
    primary_score = evidence.get(primary_family, {}).get("score", 0) if primary_family else 0

    secondary_families: List[str] = []
    for family, ev in ranked:
        if family == primary_family or ev["score"] < 20:
            continue
        if ev["source_files"] > 0 or ev["score"] >= max(20, int(primary_score * 0.12)):
            secondary_families.append(family)

    labels = {
        "python": _LANGUAGE_FAMILY_LABELS["python"],
        "javascript": _js_label(evidence["javascript"]),
    }
    root_manifest_families = {
        family
        for family, ev in evidence.items()
        if any(_is_root_file(str(path)) for path in ev.get("manifests", []))
    }
    conflicting_manifests = bool(
        primary_family
        and len(root_manifest_families) > 1
        and any(f != primary_family for f in root_manifest_families)
    )

    return {
        "primary_family": primary_family,
        "primary_language": labels.get(primary_family, "") if primary_family else "",
        "secondary_families": secondary_families,
        "secondary_languages": [labels[f] for f in secondary_families],
        "language_scores": {labels[k]: int(v["score"]) for k, v in evidence.items() if v["score"] > 0},
        "evidence": {labels[k]: dict(v) for k, v in evidence.items() if v["score"] > 0},
        "conflicting_manifests": conflicting_manifests,
    }


def detect_stack(repo: str) -> List[str]:
    langs = detect_languages(repo)
    stack: List[str] = []
    if langs.get("primary_language"):
        stack.append(str(langs["primary_language"]))
    stack.extend(str(l) for l in langs.get("secondary_languages", []))
    # Non Python/JS stacks still use manifest presence because they do not drive
    # command derivation in this MVP.
    if _has(repo, "go.mod"):
        stack.append("Go")
    if _has(repo, "Cargo.toml"):
        stack.append("Rust")
    if _has(repo, "pom.xml") or _has(repo, "build.gradle") or _has(repo, "build.gradle.kts"):
        stack.append("Java/JVM")
    if _has(repo, "Gemfile"):
        stack.append("Ruby")
    if _has(repo, "composer.json"):
        stack.append("PHP")
    return list(dict.fromkeys(stack))


def _package_json(repo: str) -> Dict[str, Any]:
    if not _has(repo, "package.json"):
        return {}
    try:
        return json.loads(_read(os.path.join(repo, "package.json"))) or {}
    except (ValueError, TypeError):
        return {}


def _pyproject(repo: str) -> Dict[str, Any]:
    return _toml_path(os.path.join(repo, "pyproject.toml"))


def _toml_path(path: str) -> Dict[str, Any]:
    if not (os.path.isfile(path) and tomllib):
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh) or {}
    except Exception:
        return {}


def _makefile_targets(repo: str) -> List[str]:
    txt = _read(os.path.join(repo, "Makefile")) if _has(repo, "Makefile") else ""
    targets: List[str] = []
    for match in re.finditer(r"(?m)^([A-Za-z0-9_\-\s]+):", txt):
        for target in match.group(1).split():
            if target and target not in targets:
                targets.append(target)
    return targets


def _package_manager(repo: str) -> str:
    if _has(repo, "pnpm-lock.yaml"):
        return "pnpm"
    if _has(repo, "yarn.lock"):
        return "yarn"
    return "npm"


def _script_command(manager: str, script: str) -> str:
    if manager == "npm":
        return f"npm run {script}"
    return f"{manager} {script}"


def _prefix_command_for_package(command: str, package_rel: str) -> str:
    cmd = str(command or "").strip()
    rel = package_rel.strip("/").replace("\\", "/")
    if not cmd or cmd.upper() == _UNKNOWN or not rel:
        return cmd
    if cmd.startswith("make "):
        target = cmd.split(" ", 1)[1].strip()
        return f"make -C {rel} {target}"
    return f"cd {rel} && {cmd}"


def _known_file(repo: str, rel: str) -> bool:
    return os.path.isfile(os.path.join(repo, rel.replace("/", os.sep)))


def _has_pytest_evidence(repo: str, py: Dict[str, Any]) -> bool:
    tool = py.get("tool") if isinstance(py.get("tool"), dict) else {}
    if "pytest" in tool:
        return True
    if _has(repo, "pytest.ini"):
        return True
    if _has(repo, "tox.ini") and "pytest" in _read(os.path.join(repo, "tox.ini"), 32768).lower():
        return True
    for rel in _candidate_requirement_files(repo):
        names = {
            _clean_dep_name(line).lower()
            for line in _read(os.path.join(repo, rel.replace("/", os.sep)), 32768).splitlines()
        }
        if "pytest" in names:
            return True
    return False


def _derive_python_commands(repo: str, make_targets: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    cmds = {slot: _UNKNOWN for slot in _COMMAND_SLOTS}
    conf = {slot: "low" for slot in _COMMAND_SLOTS}
    py = _pyproject(repo)
    lower_targets = {t.lower(): t for t in make_targets}

    if "test" in lower_targets:
        cmds["test"] = f"make {lower_targets['test']}"
        conf["test"] = "high"
    elif _known_file(repo, "tests/runtests.py"):
        cmds["test"] = "python tests/runtests.py"
        conf["test"] = "high"
    elif _has(repo, "tox.ini"):
        cmds["test"] = "tox"
        conf["test"] = "medium"
    elif _has_pytest_evidence(repo, py):
        cmds["test"] = "pytest"
        conf["test"] = "high"

    if "build" in lower_targets:
        cmds["build"] = f"make {lower_targets['build']}"
        conf["build"] = "high"
    elif py.get("build-system"):
        cmds["build"] = "python -m build"
        conf["build"] = "high"
    elif _has(repo, "setup.py") or _has(repo, "setup.cfg"):
        cmds["build"] = "python -m build"
        conf["build"] = "medium"

    if "lint" in lower_targets:
        cmds["lint"] = f"make {lower_targets['lint']}"
        conf["lint"] = "high"
    else:
        tool = py.get("tool") if isinstance(py.get("tool"), dict) else {}
        setup_cfg = _read(os.path.join(repo, "setup.cfg"), 32768) if _has(repo, "setup.cfg") else ""
        if "ruff" in tool or _has(repo, "ruff.toml"):
            cmds["lint"] = "ruff check ."
            conf["lint"] = "high"
        elif _has(repo, ".flake8") or "flake8" in setup_cfg.lower():
            cmds["lint"] = "flake8"
            conf["lint"] = "medium"
        elif "black" in tool:
            cmds["lint"] = "black --check ."
            conf["lint"] = "medium"

    if "run" in lower_targets:
        cmds["run"] = f"make {lower_targets['run']}"
        conf["run"] = "high"
    elif "start" in lower_targets:
        cmds["run"] = f"make {lower_targets['start']}"
        conf["run"] = "high"
    elif _has(repo, "manage.py"):
        cmds["run"] = "python manage.py runserver"
        conf["run"] = "medium"
    else:
        for rel in ("main.py", "app.py", "server.py", "run.py"):
            if _known_file(repo, rel):
                cmds["run"] = f"python {rel}"
                conf["run"] = "medium"
                break

    return cmds, conf


def _derive_javascript_commands(repo: str, make_targets: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    cmds = {slot: _UNKNOWN for slot in _COMMAND_SLOTS}
    conf = {slot: "low" for slot in _COMMAND_SLOTS}
    pkg = _package_json(repo)
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    manager = _package_manager(repo)
    if scripts:
        for key, slot in (("build", "build"), ("test", "test"), ("lint", "lint"), ("dev", "run"), ("start", "run")):
            if key in scripts and cmds[slot] == _UNKNOWN:
                cmds[slot] = _script_command(manager, key)
                conf[slot] = "high"

    lower_targets = {t.lower(): t for t in make_targets}
    for key, slot in (("build", "build"), ("test", "test"), ("lint", "lint"), ("run", "run"), ("start", "run")):
        if cmds[slot] == _UNKNOWN and key in lower_targets:
            cmds[slot] = f"make {lower_targets[key]}"
            conf[slot] = "medium"
    return cmds, conf


def derive_commands(repo: str, language_info: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    language_info = language_info or detect_languages(repo)
    family = str(language_info.get("primary_family") or "")
    make_targets = _makefile_targets(repo)
    if family == "python":
        cmds, conf = _derive_python_commands(repo, make_targets)
    elif family == "javascript":
        cmds, conf = _derive_javascript_commands(repo, make_targets)
    else:
        cmds = {slot: _UNKNOWN for slot in _COMMAND_SLOTS}
        conf = {slot: "low" for slot in _COMMAND_SLOTS}

    # Deployment is not a primary language signal, but older generated files expose
    # it. Keep it only when explicit infrastructure evidence exists.
    for tgt in make_targets:
        t = tgt.lower()
        if t == "deploy" and "deploy" not in cmds:
            cmds["deploy"] = f"make {tgt}"
            conf["deploy"] = "high"
    if "deploy" not in cmds:
        if _has(repo, "docker-compose.yml") or _has(repo, "docker-compose.yaml") or _has(repo, "compose.yaml"):
            cmds["deploy"] = "docker compose up -d"
            conf["deploy"] = "medium"
        elif _has(repo, "Dockerfile"):
            cmds["deploy"] = "docker build -t app . && docker run app"
            conf["deploy"] = "medium"
    return cmds, conf


def detect_commands(repo: str) -> Dict[str, str]:
    cmds, _ = derive_commands(repo)
    return cmds


def _clean_dep_name(raw: Any) -> str:
    s = str(raw or "").strip().strip("\"'")
    if not s or s.startswith("#"):
        return ""
    if s.startswith(("-r ", "--requirement", "--constraint", "-c ")):
        return ""
    if s.startswith("-e ") and "#egg=" in s:
        s = s.split("#egg=", 1)[1]
    elif s.startswith("-"):
        return ""
    s = s.split("#", 1)[0].strip()
    s = s.split(";", 1)[0].strip()
    if " @ " in s:
        s = s.split(" @ ", 1)[0].strip()
    tokens = s.split()
    version_ops = ("==", "===", "~=", "!=", "<=", ">=", "<", ">")
    if len(tokens) > 1 and not tokens[1].startswith(version_ops):
        return ""
    s = re.split(r"\s*(?:===|==|~=|!=|<=|>=|<|>)", s, maxsplit=1)[0].strip()
    s = s.split("[", 1)[0].strip()
    s = re.split(r"\s+", s, maxsplit=1)[0].strip(" ,")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", s):
        return ""
    if s.lower() in {"python", "pip", "setuptools", "wheel"}:
        return ""
    return s


def _add_dep(out: List[str], raw: Any) -> None:
    name = _clean_dep_name(raw)
    if name:
        out.append(name)


def _pyproject_files(repo: str) -> List[str]:
    files: List[str] = []
    if _has(repo, "pyproject.toml"):
        files.append("pyproject.toml")
    for rel in _iter_repo_files(repo):
        if rel == "pyproject.toml":
            continue
        if rel.lower().endswith("/pyproject.toml") and len(_rel_parts(rel)) <= 4:
            files.append(rel)
            if len(files) >= 24:
                break
    return files


def _candidate_requirement_files(repo: str) -> List[str]:
    names = [
        "requirements.txt",
        "requirements/default.txt",
        "requirements/base.txt",
        "requirements-dev.txt",
        "dev-requirements.txt",
        "requirements/dev.txt",
        "requirements/test.txt",
    ]
    out = [n for n in names if _has(repo, n)]
    try:
        req_dir = os.path.join(repo, "requirements")
        if os.path.isdir(req_dir):
            for name in sorted(os.listdir(req_dir)):
                rel = f"requirements/{name}"
                if name.endswith(".txt") and rel not in out:
                    out.append(rel)
    except OSError:
        pass
    return out


def _deps_from_pyproject(repo: str) -> List[str]:
    deps: List[str] = []
    for rel in _pyproject_files(repo):
        py = _toml_path(os.path.join(repo, rel.replace("/", os.sep)))
        proj = py.get("project") if isinstance(py.get("project"), dict) else {}
        for d in (proj.get("dependencies") or []):
            _add_dep(deps, d)

        optional = proj.get("optional-dependencies") if isinstance(proj.get("optional-dependencies"), dict) else {}
        if not deps and isinstance(optional, dict):
            for values in optional.values():
                for d in values or []:
                    _add_dep(deps, d)

        tool = py.get("tool") if isinstance(py.get("tool"), dict) else {}
        poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
        poetry_deps = poetry.get("dependencies") if isinstance(poetry.get("dependencies"), dict) else {}
        for name in poetry_deps:
            if str(name).lower() != "python":
                _add_dep(deps, name)

        if not deps:
            legacy_dev = poetry.get("dev-dependencies") if isinstance(poetry.get("dev-dependencies"), dict) else {}
            for name in legacy_dev:
                _add_dep(deps, name)
        group = poetry.get("group") if isinstance(poetry.get("group"), dict) else {}
        if not deps and isinstance(group, dict):
            for group_data in group.values():
                group_deps = group_data.get("dependencies") if isinstance(group_data, dict) else {}
                if isinstance(group_deps, dict):
                    for name in group_deps:
                        _add_dep(deps, name)
    return deps


def _deps_from_requirements(repo: str) -> List[str]:
    deps: List[str] = []
    for rel in _candidate_requirement_files(repo):
        txt = _read(os.path.join(repo, rel.replace("/", os.sep)), 32768)
        for raw in txt.splitlines():
            _add_dep(deps, raw)
    return deps


def _deps_from_setup_cfg(repo: str) -> List[str]:
    if not _has(repo, "setup.cfg"):
        return []
    cp = configparser.ConfigParser()
    try:
        cp.read(os.path.join(repo, "setup.cfg"), encoding="utf-8")
    except Exception:
        return []
    deps: List[str] = []
    if cp.has_option("options", "install_requires"):
        for raw in cp.get("options", "install_requires").splitlines():
            _add_dep(deps, raw)
    return deps


def _deps_from_setup_py(repo: str) -> List[str]:
    if not _has(repo, "setup.py"):
        return []
    txt = _read(os.path.join(repo, "setup.py"), 65536)
    deps: List[str] = []
    for match in re.finditer(r"(?:install_requires|requires)\s*=\s*(\[[\s\S]*?\])", txt):
        try:
            values = ast.literal_eval(match.group(1))
        except Exception:
            continue
        if isinstance(values, (list, tuple)):
            for raw in values:
                _add_dep(deps, raw)
    return deps


def _collect_python_dependencies(repo: str) -> List[str]:
    deps: List[str] = []
    deps.extend(_deps_from_pyproject(repo))
    deps.extend(_deps_from_setup_cfg(repo))
    deps.extend(_deps_from_setup_py(repo))
    deps.extend(_deps_from_requirements(repo))
    return deps


def _deps_from_package_json_obj(pkg: Dict[str, Any]) -> List[str]:
    deps: List[str] = []
    for section in ("dependencies", "peerDependencies", "optionalDependencies", "devDependencies"):
        values = pkg.get(section)
        if isinstance(values, dict):
            deps.extend(str(k) for k in values)
    return deps


def _collect_javascript_dependencies(repo: str) -> List[str]:
    deps: List[str] = []
    pkg = _package_json(repo)
    deps.extend(_deps_from_package_json_obj(pkg))
    if not deps and _has(repo, "package-lock.json"):
        try:
            lock = json.loads(_read(os.path.join(repo, "package-lock.json"), 65536)) or {}
        except (ValueError, TypeError):
            lock = {}
        root = (lock.get("packages") or {}).get("") if isinstance(lock.get("packages"), dict) else {}
        if isinstance(root, dict):
            deps.extend(_deps_from_package_json_obj(root))
    return deps


def detect_dependencies(repo: str, language_info: Optional[Dict[str, Any]] = None) -> List[str]:
    language_info = language_info or detect_languages(repo)
    family = str(language_info.get("primary_family") or "")
    if family == "python":
        deps = _collect_python_dependencies(repo)
    elif family == "javascript":
        deps = _collect_javascript_dependencies(repo)
    else:
        deps = []
    # dedupe, keep order, cap
    seen: set = set()
    out: List[str] = []
    for d in deps:
        name = _clean_dep_name(d)
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out[:12]


def _project_metadata(repo: str) -> Dict[str, str]:
    py = _pyproject(repo)
    project = py.get("project") if isinstance(py.get("project"), dict) else {}
    if project:
        return {
            "name": str(project.get("name") or "").strip(),
            "description": str(project.get("description") or "").strip(),
        }
    pkg = _package_json(repo)
    if pkg:
        return {
            "name": str(pkg.get("name") or "").strip(),
            "description": str(pkg.get("description") or "").strip(),
        }
    return {"name": "", "description": ""}


def _has_package_manifest(path: str) -> bool:
    return any(os.path.isfile(os.path.join(path, name)) for name in (
        "pyproject.toml",
        "package.json",
        "setup.cfg",
        "setup.py",
        "Makefile",
    ))


def _count_source_files(repo: str, family: str) -> int:
    count = 0
    for rel in _iter_repo_files(repo, max_files=20000):
        if _is_source_file_for_family(rel, family):
            count += 1
    return count


def _owned_modules(package_abs: str, family: str) -> List[str]:
    owned: List[str] = []
    try:
        for entry in sorted(os.listdir(package_abs)):
            full = os.path.join(package_abs, entry)
            if not os.path.isdir(full) or entry.startswith(".") or entry in _NOISE_DIRS:
                continue
            if entry.lower() in {"tests", "test", "testing", "scripts", "docs", "examples"}:
                continue
            if family == "python" and os.path.isfile(os.path.join(full, "__init__.py")):
                owned.append(entry)
            elif any(_is_source_file_for_family(os.path.join(entry, f).replace("\\", "/"), family) for f in os.listdir(full)):
                owned.append(entry)
    except OSError:
        pass
    return owned[:4]


def _package_commands(repo: str, package_rel: str, language_info: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    package_abs = os.path.join(repo, package_rel.replace("/", os.sep))
    commands, confidence = derive_commands(package_abs, language_info)
    out: Dict[str, str] = {}
    out_conf: Dict[str, str] = {}
    for key in ("test", "build", "lint", "run"):
        value = commands.get(key)
        if value and str(value).upper() != _UNKNOWN:
            out[key] = _prefix_command_for_package(value, package_rel)
            out_conf[key] = confidence.get(key, "medium")

    targets = {t.lower(): t for t in _makefile_targets(package_abs)}
    for target in ("type", "integration_tests", "check_imports", "check-lock"):
        if target in targets and target not in out:
            out[target] = f"make -C {package_rel} {targets[target]}"
            out_conf[target] = "medium"
    return out, out_conf


def _workspace_candidates(repo: str) -> List[str]:
    candidates: List[str] = []
    for root_name in _WORKSPACE_DIRS:
        root = os.path.join(repo, root_name)
        if not os.path.isdir(root):
            continue
        try:
            child_names = sorted(os.listdir(root))
        except OSError:
            continue
        for child in child_names:
            child_abs = os.path.join(root, child)
            if not os.path.isdir(child_abs) or child.startswith(".") or child in _NOISE_DIRS:
                continue
            rel = f"{root_name}/{child}".replace("\\", "/")
            if _has_package_manifest(child_abs):
                candidates.append(rel)
                continue
            # Workspace groups such as libs/partners own many real child packages
            # even when the aggregate directory has no pyproject of its own.
            child_packages = 0
            try:
                for grand in os.listdir(child_abs):
                    grand_abs = os.path.join(child_abs, grand)
                    if os.path.isdir(grand_abs) and _has_package_manifest(grand_abs):
                        child_packages += 1
            except OSError:
                child_packages = 0
            if child_packages >= 2:
                candidates.append(rel)
    return candidates


def _package_rank(pkg: Dict[str, Any]) -> Tuple[int, str]:
    rel = str(pkg.get("path") or "")
    score = int(pkg.get("source_files") or 0)
    lowered = rel.lower()
    if "core" in lowered:
        score += 80
    if lowered.endswith("/langchain") or lowered.endswith("/langchain_v1"):
        score += 60
    if "partner" in lowered:
        score += 45
    if "text-split" in lowered:
        score += 40
    if "standard-test" in lowered or lowered.endswith("/tests"):
        score -= 20
    if pkg.get("commands"):
        score += 25
    if pkg.get("dependencies"):
        score += 20
    return (-score, rel)


def detect_workspace_packages(repo: str, language_info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Derive package-level context for workspace/monorepo layouts."""
    if not os.path.isdir(repo):
        return []
    candidates = _workspace_candidates(repo)
    if len(candidates) < 2:
        return []

    packages: List[Dict[str, Any]] = []
    seen: set = set()
    for rel in candidates:
        if rel in seen:
            continue
        seen.add(rel)
        package_abs = os.path.join(repo, rel.replace("/", os.sep))
        info = detect_languages(package_abs)
        family = str(info.get("primary_family") or (language_info or {}).get("primary_family") or "python")
        metadata = _project_metadata(package_abs)
        source_files = _count_source_files(package_abs, family)
        child_packages = 0
        try:
            child_packages = sum(
                1 for name in os.listdir(package_abs)
                if os.path.isdir(os.path.join(package_abs, name)) and _has_package_manifest(os.path.join(package_abs, name))
            )
        except OSError:
            child_packages = 0
        if source_files == 0 and child_packages == 0:
            continue

        commands, command_confidence = _package_commands(repo, rel, info)
        deps = detect_dependencies(package_abs, info)
        reps = _representative_files(
            [p for p in _collect_files_under(repo, rel, exts=_source_extensions(family), limit=120) if not _is_test_path(p)],
            limit=3,
        )
        purpose = metadata.get("description") or _purpose_for_group(rel)[0]
        if child_packages and not metadata.get("description"):
            purpose = f"{_purpose_for_group(rel)[0]} across {child_packages} child packages"
        owners = _owned_modules(package_abs, family)
        if not owners and metadata.get("name"):
            owners = [metadata["name"]]

        packages.append({
            "path": rel,
            "name": metadata.get("name") or os.path.basename(rel),
            "purpose": purpose or "UNKNOWN",
            "owner": ", ".join(owners[:3]) if owners else rel,
            "commands": commands,
            "command_confidence": command_confidence,
            "dependencies": deps[:8],
            "representative_files": reps,
            "source_files": source_files,
            "child_packages": child_packages,
            "confidence": "high" if commands and (deps or child_packages) else "medium" if commands or deps else "low",
        })

    packages = sorted(packages, key=_package_rank)
    return packages[:7]


def detect_conventions(repo: str) -> List[str]:
    conv: List[str] = []
    if any(_has(repo, n) for n in (".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.cjs", "eslint.config.js", "eslint.config.mjs")):
        conv.append("ESLint")
    if any(_has(repo, n) for n in (".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js")):
        conv.append("Prettier")
    if _has(repo, "tsconfig.json"):
        if '"strict": true' in _read(os.path.join(repo, "tsconfig.json"), 8192):
            conv.append("TypeScript (strict)")
        else:
            conv.append("TypeScript")
    py = _pyproject(repo)
    tool = py.get("tool") if isinstance(py.get("tool"), dict) else {}
    if "black" in tool:
        conv.append("Black")
    if "ruff" in tool:
        conv.append("Ruff")
    if "mypy" in tool or _has(repo, "mypy.ini"):
        conv.append("mypy")
    if _has(repo, ".editorconfig"):
        conv.append("EditorConfig")
    return conv


def repo_structure(repo: str) -> List[str]:
    out: List[str] = []
    try:
        for entry in sorted(os.listdir(repo)):
            full = os.path.join(repo, entry)
            if os.path.isdir(full) and entry not in _NOISE_DIRS and not entry.startswith("."):
                out.append(entry + "/")
    except OSError:
        return []
    return out[:12]


def _entry_points(repo: str) -> List[str]:
    candidates = [
        "main.py", "app.py", "server.py", "run.py", "manage.py", "__main__.py",
        "src/index.ts", "src/index.js", "index.ts", "index.js", "src/main.ts", "cmd/main.go", "main.go",
    ]
    found = [c for c in candidates if _has(repo, c)]
    pkg = _package_json(repo)
    if isinstance(pkg.get("main"), str):
        found.append(pkg["main"])
    seen: set = set()
    out: List[str] = []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:5]


def _repo_file_exists(repo: str, rel: str) -> bool:
    return bool(rel) and os.path.isfile(os.path.join(repo, rel.replace("/", os.sep)))


def resolve_repository_file(repo: str, ref: Any) -> Optional[str]:
    """Resolve a scan/module identifier to a real repo-relative file path.

    Returns None when the path cannot be proven to exist. This is intentionally
    conservative: agents can open real paths, but a fake path destroys trust.
    """
    raw = str(ref or "").strip()
    if not raw:
        return None
    raw = raw.replace("\\", "/").strip("/")
    candidates: List[str] = []

    if _repo_file_exists(repo, raw):
        return raw
    candidates.append(raw)

    if raw.endswith("/"):
        candidates.append(raw + "__init__.py")
    elif "/" in raw:
        base, ext = os.path.splitext(raw)
        if not ext:
            candidates.extend([raw + ".py", raw + "/__init__.py", raw + ".js", raw + ".ts", raw + ".tsx"])
    elif "." in raw:
        mod = raw.replace(".", "/")
        candidates.extend([mod + ".py", mod + "/__init__.py"])

    seen: set = set()
    for cand in candidates:
        rel = cand.strip("/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        if _repo_file_exists(repo, rel):
            return rel
    return None


def _derive_critical_files(repo: str, refs: Iterable[Any]) -> Tuple[List[str], List[str]]:
    resolved: List[str] = []
    unresolved: List[str] = []
    seen: set = set()
    for ref in refs:
        path = resolve_repository_file(repo, ref)
        if path:
            if path not in seen:
                seen.add(path)
                resolved.append(path)
        elif ref:
            unresolved.append(str(ref))
        if len(resolved) >= 6:
            break
    return resolved, unresolved[:8]


def _is_tooling_or_ci_path(rel: str) -> bool:
    parts = [p.lower() for p in _rel_parts(rel)]
    if not parts:
        return False
    if parts[0] in {".github", ".circleci", ".azure-pipelines", ".devcontainer"}:
        return True
    if parts[0] in {"scripts", "tools"}:
        return True
    return len(parts) >= 2 and parts[1] in {"scripts", "tools"} and parts[0] not in {"src", "lib", "libs"}


def _critical_score(repo: str, rel: str, source: str, *, degraded: bool, package_prefixes: List[str]) -> int:
    score_by_source = {
        "entrypoint": 110,
        "package": 95,
        "subsystem": 85,
        "graph": 60 if not degraded else 25,
        "risk": 55 if not degraded else 20,
    }
    score = score_by_source.get(source, 40)
    family = "javascript" if os.path.splitext(rel.lower())[1] in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"} else "python"
    if _is_source_file_for_family(rel, family):
        score += 25
    if any(rel.startswith(prefix.rstrip("/") + "/") for prefix in package_prefixes):
        score += 20
    if _is_test_path(rel):
        score -= 20
    if _is_tooling_or_ci_path(rel):
        score -= 85 if degraded else 35
    if os.path.basename(rel).lower() in {"__init__.py", "index.ts", "index.js", "main.py", "manage.py"}:
        score += 10
    return score


def _derive_weighted_critical_files(
    repo: str,
    candidates: Iterable[Tuple[str, Any]],
    *,
    degraded: bool,
    package_prefixes: List[str],
) -> Tuple[List[str], List[str], List[Dict[str, Any]], List[str]]:
    ranked: List[Tuple[int, str, str]] = []
    unresolved: List[str] = []
    suppressed: List[str] = []
    seen_refs: set = set()
    for source, ref in candidates:
        raw = str(ref or "").strip()
        if not raw or raw in seen_refs:
            continue
        seen_refs.add(raw)
        path = resolve_repository_file(repo, raw)
        if not path:
            unresolved.append(raw)
            continue
        score = _critical_score(repo, path, source, degraded=degraded, package_prefixes=package_prefixes)
        if degraded and score < 50:
            suppressed.append(path)
            continue
        ranked.append((score, path, source))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    resolved: List[str] = []
    ranking: List[Dict[str, Any]] = []
    seen_paths: set = set()
    for score, path, source in ranked:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        resolved.append(path)
        ranking.append({"path": path, "source": source, "score": score})
        if len(resolved) >= 6:
            break
    return resolved, unresolved[:8], ranking, suppressed[:8]


def _source_extensions(primary_family: str) -> set:
    if primary_family == "javascript":
        return {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
    return {".py", ".pyi"}


def _is_source_file_for_family(rel: str, family: str) -> bool:
    ext = os.path.splitext(rel.lower())[1]
    if family == "javascript" and rel.lower().endswith(".d.ts"):
        return False
    return ext in _source_extensions(family)


_PURPOSE_RULES: List[Tuple[Tuple[str, ...], str]] = [
    (("auth", "login", "session"), "authentication and session handling"),
    (("db", "database", "models", "migrations"), "database layer"),
    (("api", "http", "views", "routes", "rest"), "API and HTTP surface"),
    (("cli", "bin", "commands", "management"), "command-line interface"),
    (("template", "templates", "render", "rendering"), "templates and rendering"),
    (("task", "tasks", "queue", "worker", "beat"), "task queue and worker runtime"),
    (("core", "engine", "runtime"), "core engine"),
    (("integration", "integrations", "partners", "adapters", "contrib"), "integrations and extensions"),
    (("util", "utils", "common", "helpers"), "shared utilities"),
    (("config", "conf", "settings"), "configuration"),
    (("forms", "validation"), "forms and validation"),
    (("admin",), "administrative interface"),
    (("test", "tests", "testing", "t"), "test suite"),
    (("docs", "documentation"), "documentation"),
    (("package", "packaging", "build"), "package management"),
]


def _purpose_tokens(parts: List[str]) -> set:
    tokens = set(parts)
    for part in parts:
        for token in re.split(r"[^a-z0-9]+", part):
            if not token:
                continue
            tokens.add(token)
            if token.endswith("s") and len(token) > 3:
                tokens.add(token[:-1])
    return tokens


def _purpose_for_group(path: str) -> Tuple[str, str]:
    parts = [p.lower().replace("-", "_") for p in _rel_parts(path)]
    tokens = _purpose_tokens(parts)
    for keys, purpose in _PURPOSE_RULES:
        if any(k in tokens or (len(k) >= 5 and any(t.startswith(k) for t in tokens)) for k in keys):
            return purpose, "high"
    if parts:
        return "core package area", "medium"
    return "UNKNOWN", "low"


def _display_subsystem_name(path: str) -> str:
    if path == "tests":
        return "tests"
    if path == "docs":
        return "documentation"
    if path == "config":
        return "configuration"
    return path.replace("\\", "/").strip("/")


def _representative_files(files: List[str], limit: int = 3) -> List[str]:
    def rank(rel: str) -> Tuple[int, str]:
        base = os.path.basename(rel).lower()
        preferred = (
            "__init__.py", "base.py", "main.py", "index.ts", "index.js",
            "models.py", "views.py", "api.py", "routes.py", "settings.py",
            "README.md", "README.rst", "pyproject.toml", "package.json",
        )
        score = preferred.index(base) if base in preferred else len(preferred)
        return score, rel

    return sorted(list(dict.fromkeys(files)), key=rank)[:limit]


def _source_group_key(rel: str) -> str:
    parts = _rel_parts(rel)
    if not parts:
        return ""
    base = os.path.basename(rel)
    if parts[0] == "src" and len(parts) >= 3:
        root = f"src/{parts[1]}"
        if len(parts) >= 4 and base != "__init__.py":
            return f"{root}/{parts[2]}"
        return root
    if parts[0] == "libs" and len(parts) >= 2:
        if parts[1] == "partners" and len(parts) >= 3:
            return "libs/partners"
        return f"libs/{parts[1]}"
    if len(parts) >= 3 and _repo_style_package_segment(parts[0]):
        if base == "__init__.py":
            return parts[0]
        return f"{parts[0]}/{parts[1]}"
    if len(parts) >= 2:
        return parts[0]
    return ""


def _repo_style_package_segment(segment: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", segment or ""))


def _collect_files_under(repo: str, prefix: str, *, exts: Optional[set] = None, limit: int = 200) -> List[str]:
    out: List[str] = []
    prefix_norm = prefix.strip("/").lower()
    for rel in _iter_repo_files(repo):
        lower = rel.lower()
        if not lower.startswith(prefix_norm + "/"):
            continue
        if exts is not None and os.path.splitext(lower)[1] not in exts:
            continue
        out.append(rel)
        if len(out) >= limit:
            break
    return out


def derive_subsystems(repo: str, index: Dict[str, Any], language_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive compact, path-backed subsystem groups.

    Groups are based on source layout and generic engineering vocabulary. They do
    not infer business/domain intent.
    """
    if not os.path.isdir(repo):
        return []
    family = str(language_info.get("primary_family") or "python")
    groups: Dict[str, List[str]] = {}
    for rel in _iter_repo_files(repo):
        if not _is_source_file_for_family(rel, family):
            continue
        parts = _rel_parts(rel)
        if not parts or parts[0].lower() in {"docs", "examples", "benchmarks"}:
            continue
        if _is_test_path(rel):
            groups.setdefault("tests", []).append(rel)
            continue
        key = _source_group_key(rel)
        if key:
            groups.setdefault(key, []).append(rel)

    # Add non-source handoff groups only when there is room and real files exist.
    if "docs" not in groups and os.path.isdir(os.path.join(repo, "docs")):
        docs = _collect_files_under(repo, "docs", exts={".md", ".rst", ".txt"}, limit=20)
        if docs:
            groups["docs"] = docs
    config_files = [
        rel for rel in (
            "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini",
            "package.json", "tsconfig.json", "Makefile", ".flake8",
        )
        if _repo_file_exists(repo, rel)
    ]
    if config_files:
        groups["config"] = config_files

    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    out: List[Dict[str, Any]] = []
    for key, files in ranked:
        if not files:
            continue
        # Avoid file-like subsystem names unless this is truly the only tiny group.
        if os.path.splitext(key)[1] and len(groups) > 1:
            continue
        purpose, purpose_conf = _purpose_for_group(key)
        reps = _representative_files(files)
        if len(files) >= 8 and purpose_conf != "low":
            confidence = "high"
        elif len(files) >= 2:
            confidence = "medium"
        else:
            confidence = "low"
        out.append({
            "name": _display_subsystem_name(key),
            "purpose": purpose,
            "representative_files": reps,
            "confidence": confidence,
            "files": len(files),
        })
        if len(out) >= 6:
            break

    if not out:
        # Preserve the old index as weak evidence only when no path-backed groups
        # can be derived.
        subs = sorted(
            (s for s in index.get("subsystems", []) if s.get("role_counts", {}).get("production_code", 0) > 0),
            key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
        )
        for s in subs[:3]:
            name = str(s.get("name", "")).strip()
            if name:
                out.append({
                    "name": name,
                    "purpose": "UNKNOWN",
                    "representative_files": [],
                    "confidence": "low",
                    "files": int(s.get("role_counts", {}).get("production_code", 0)),
                })
    return out


def _language_evidence_summary(language_info: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    evidence = language_info.get("evidence") if isinstance(language_info.get("evidence"), dict) else {}
    for label, ev in evidence.items():
        if not isinstance(ev, dict):
            continue
        summary[label] = {
            "score": int(ev.get("score", 0)),
            "source_files": int(ev.get("source_files", 0)),
            "test_files": int(ev.get("test_files", 0)),
            "manifest_files": int(ev.get("manifest_files", 0)),
            "lock_files": int(ev.get("lock_files", 0)),
            "build_files": int(ev.get("build_files", 0)),
            "manifests": list(ev.get("manifests", []))[:8],
        }
    return summary


def _score_derivation_confidence(
    *,
    language_info: Dict[str, Any],
    commands: Dict[str, str],
    command_confidence: Dict[str, str],
    deps: List[str],
    summary: str,
    conventions: List[str],
    gh_label: str,
    degraded: bool,
    modules: int,
    edges: int,
) -> Tuple[str, List[str]]:
    points = 6
    reasons: List[str] = []

    def penalize(amount: int, reason: str) -> None:
        nonlocal points
        points -= amount
        reasons.append(reason)

    if not language_info.get("primary_language"):
        penalize(3, "primary language unknown")
    if commands.get("test") == _UNKNOWN:
        penalize(2, "test command unknown")
    if commands.get("build") == _UNKNOWN:
        penalize(1, "build command unknown")
    if not deps:
        penalize(2, "dependencies missing")
    if degraded or gh_label in {"degraded", "partial", "unsupported"} or (modules > 0 and edges == 0):
        penalize(2, f"dependency graph is {gh_label}")
    elif gh_label == "watch":
        penalize(1, "dependency graph needs watch")
    if language_info.get("conflicting_manifests"):
        penalize(1, "conflicting root manifests")
    if not summary:
        penalize(1, "readme summary missing")
    if not conventions:
        penalize(1, "tooling conventions missing")

    unknown_slots = [slot for slot in _COMMAND_SLOTS if commands.get(slot) == _UNKNOWN]
    if len(unknown_slots) >= 3:
        penalize(1, "most command slots unknown")

    evidence = language_info.get("evidence") if isinstance(language_info.get("evidence"), dict) else {}
    primary = str(language_info.get("primary_language") or "")
    primary_ev = evidence.get(primary) if isinstance(evidence.get(primary), dict) else {}
    if primary_ev and int(primary_ev.get("source_files", 0)) < 2 and int(primary_ev.get("manifest_files", 0)) < 2:
        penalize(1, "low primary-language evidence")

    confidence = "high" if points >= 5 else "medium" if points >= 3 else "low"

    # Hard caps: never high when essentials are missing or structure is degraded.
    order = {"low": 0, "medium": 1, "high": 2}

    def cap(level: str) -> None:
        nonlocal confidence
        if order[confidence] > order[level]:
            confidence = level

    if commands.get("test") == _UNKNOWN or not deps:
        cap("medium")
    if degraded or gh_label in {"degraded", "partial", "unsupported"} or (modules > 0 and edges == 0):
        cap("medium")
        if commands.get("test") == _UNKNOWN:
            cap("low")
    if not language_info.get("primary_language"):
        cap("low")

    if not reasons:
        reasons.append("strong primary-language, dependency, command, and graph evidence")
    return confidence, reasons[:8]


def derive_agent_context(repo_path: str, scan: Dict[str, Any], index: Dict[str, Any]) -> Dict[str, Any]:
    """Build the agent_context section of repository memory. Fully derived; safe with
    missing files (returns minimal context)."""
    repo = os.path.abspath(repo_path or "")
    scan = scan or {}
    index = index or {}

    language_info = detect_languages(repo) if os.path.isdir(repo) else {}
    summary = _readme_summary(repo) if os.path.isdir(repo) else ""
    stack = detect_stack(repo) if os.path.isdir(repo) else []
    commands, command_confidence = derive_commands(repo, language_info) if os.path.isdir(repo) else ({}, {})
    deps = detect_dependencies(repo, language_info) if os.path.isdir(repo) else []
    conventions = detect_conventions(repo) if os.path.isdir(repo) else []
    structure = repo_structure(repo) if os.path.isdir(repo) else []

    # From analysis (scan/index) — reuse, don't recompute.
    modules = int(scan.get("module_count", 0))
    edges = int(scan.get("dependency_edges", 0))
    cycles = int(scan.get("import_cycle_count", 0) or 0)
    gh = scan.get("graph_health")
    gh_label = gh.get("label") if isinstance(gh, dict) else (str(gh) if gh else "unknown")
    degraded = bool(scan.get("degraded"))

    graph_degraded = bool(degraded or gh_label in {"degraded", "partial", "unsupported"} or (modules > 0 and edges == 0))
    hubs = [h.get("module", "") for h in (scan.get("top_hubs") or [])[:8] if h.get("module")]
    risks: List[str] = []
    for r in (scan.get("top_risks") or [])[:8]:
        risks.append(str(r.get("module") or r.get("path") or "") if isinstance(r, dict) else str(r or ""))
    risks = [r for r in risks if r]

    key_subsystems = derive_subsystems(repo, index, language_info) if os.path.isdir(repo) else []
    packages = detect_workspace_packages(repo, language_info) if os.path.isdir(repo) else []

    entrypoints = _entry_points(repo) if os.path.isdir(repo) else []
    package_refs = [
        rel
        for pkg in packages
        for rel in (pkg.get("representative_files") or [])[:2]
    ]
    subsystem_refs = [
        rel
        for sub in key_subsystems
        for rel in (sub.get("representative_files") or [])[:1]
    ]
    candidate_refs: List[Tuple[str, Any]] = []
    candidate_refs.extend(("entrypoint", ref) for ref in entrypoints)
    if graph_degraded:
        candidate_refs.extend(("package", ref) for ref in package_refs)
        candidate_refs.extend(("subsystem", ref) for ref in subsystem_refs)
        candidate_refs.extend(("graph", ref) for ref in hubs)
        candidate_refs.extend(("risk", ref) for ref in risks)
    else:
        candidate_refs.extend(("graph", ref) for ref in hubs)
        candidate_refs.extend(("risk", ref) for ref in risks)
        candidate_refs.extend(("package", ref) for ref in package_refs)
        candidate_refs.extend(("subsystem", ref) for ref in subsystem_refs)

    if os.path.isdir(repo):
        critical_files, unresolved_critical_refs, critical_ranking, suppressed_graph_refs = _derive_weighted_critical_files(
            repo,
            candidate_refs,
            degraded=graph_degraded,
            package_prefixes=[str(pkg.get("path") or "") for pkg in packages],
        )
    else:
        critical_files, unresolved_critical_refs, critical_ranking, suppressed_graph_refs = ([], [], [], [])

    display_hubs = hubs
    if graph_degraded:
        display_hubs = [
            item["path"]
            for item in critical_ranking
            if item.get("source") in {"package", "subsystem", "entrypoint"}
        ][:3]

    pitfalls: List[str] = []
    if graph_degraded and packages:
        pitfalls.append("Package sections are higher confidence than degraded graph hubs.")
    if degraded or gh_label in ("degraded", "partial", "unsupported"):
        pitfalls.append(f"Dependency graph is {gh_label} — treat structure facts as partial.")
    if cycles:
        pitfalls.append(f"{cycles} import cycle(s) present — changes can ripple unexpectedly.")
    if display_hubs:
        label = "High fan-in modules" if not graph_degraded else "Preferred source/package starting points"
        pitfalls.append(f"{label} (change with care): {', '.join(display_hubs[:3])}.")

    arch = (
        f"{modules} modules, {edges} dependency edges across "
        f"{len(index.get('subsystems', []))} subsystems; graph health: {gh_label}."
    )
    if display_hubs and not graph_degraded:
        arch += f" Most depended-on: {', '.join(display_hubs[:3])}."
    elif packages:
        arch += f" Workspace packages detected: {', '.join(str(pkg.get('path')) for pkg in packages[:4])}."

    confidence, confidence_reasons = _score_derivation_confidence(
        language_info=language_info,
        commands=commands,
        command_confidence=command_confidence,
        deps=deps,
        summary=summary,
        conventions=conventions,
        gh_label=gh_label,
        degraded=degraded,
        modules=modules,
        edges=edges,
    )

    sources = [n for n in ("README.md", "package.json", "pyproject.toml", "requirements.txt",
                           "Makefile", "tsconfig.json", "Dockerfile") if _has(repo, n)]

    return {
        "project_summary": summary,
        "primary_language": language_info.get("primary_language", ""),
        "secondary_languages": language_info.get("secondary_languages", []),
        "language_scores": language_info.get("language_scores", {}),
        "language_evidence": _language_evidence_summary(language_info),
        "stack": stack,
        "architecture_summary": arch,
        "key_subsystems": key_subsystems,
        "packages": packages,
        "critical_files": critical_files,
        "critical_file_ranking": critical_ranking,
        "suppressed_graph_refs": suppressed_graph_refs,
        "unresolved_critical_refs": unresolved_critical_refs,
        "structure": structure,
        "important_dependencies": deps,
        "conventions": conventions,
        "commands": commands,
        "command_confidence": command_confidence,
        "pitfalls": pitfalls,
        "derivation_confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "sources": sources,
    }
