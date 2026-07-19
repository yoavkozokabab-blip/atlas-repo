"""Pre-answer existence checks for entity-specific repository questions.

The copilot must not turn a failed entity lookup into a repository summary.
This module only uses persisted/indexed paths and symbol definitions; it never
falls back to semantic similarity as proof that the requested entity exists.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


_FILE_RE = re.compile(
    r"(?<![\w.-])((?:[\w.@+-]+/)*[\w.@+-]+\."
    r"(?:py|pyi|js|jsx|ts|tsx|mjs|cjs|json|ya?ml|toml|ini|cfg|conf|xml|tf|"
    r"properties|env|md|rst|txt))(?![\w.-])",
    re.IGNORECASE,
)
_DOCKERFILE_RE = re.compile(r"(?<![\w.-])((?:[\w.@+-]+/)*Dockerfile(?:\.[\w.-]+)?)(?![\w.-])", re.I)
_EXPLICIT_KIND_RE = re.compile(
    r"\b(class|function|method|config(?:uration)?|setting|environment variable|env var|file|module)\s+"
    r"(?:named\s+|called\s+)?[`'\"]?([A-Za-z_$][\w$.-]*(?:/[\w.@+-]+)*)",
    re.IGNORECASE,
)
_WHERE_RE = re.compile(
    r"\bwhere\s+(?:is|are|does|do)\s+(?:the\s+)?(.+?)"
    r"(?:\s+(?:implemented|defined|configured|handled|located|live|declared|used))?[?.!]*$",
    re.IGNORECASE,
)
_HOW_RE = re.compile(
    r"\bhow\s+does\s+(?:the\s+)?([A-Za-z_$][\w$.-]*)\s+(?:work|behave|run|load|start)[?.!]*$",
    re.IGNORECASE,
)
_GENERIC_QUESTIONS = (
    "this repository",
    "the repository",
    "this repo",
    "the repo",
    "repository do",
    "top architectural",
    "import cycles",
    "production code",
    "which files should i read",
    "request flow",
)
_BROAD_MODES = {"risk", "cycles", "context_export", "repository_understanding"}
_KIND_MAP = {
    "class": {"class", "interface", "protocol", "abstract", "registry", "middleware", "factory"},
    "function": {"function"},
    "method": {"method"},
    "config": {"config"},
    "configuration": {"config"},
    "setting": {"config"},
    "environment variable": {"config"},
    "env var": {"config"},
}


def _normal(value: str) -> str:
    return str(value or "").replace("\\", "/").strip().strip("`'\"").lower()


def _clean_entity(value: str) -> str:
    value = str(value or "").strip().strip("`'\"").strip()
    value = re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.I)
    value = re.sub(
        r"\s+(?:implemented|defined|configured|handled|located|declared|used)\s*$",
        "",
        value,
        flags=re.I,
    )
    return value.strip(" `\"'?.!,;:")


def _looks_specific(value: str) -> bool:
    if not value or len(value) > 120:
        return False
    if any(marker in value.lower() for marker in _GENERIC_QUESTIONS):
        return False
    tokens = re.findall(r"[A-Za-z0-9_$.-]+", value)
    return 1 <= len(tokens) <= 6 and any(len(token) >= 3 for token in tokens)


def extract_query_entity(question: str, mode: str = "unknown") -> Optional[Dict[str, str]]:
    """Return an entity candidate only when the question names one.

    Broad repository questions deliberately return ``None`` so normal summary,
    risk, cycle, and context-export answers keep working.
    """

    text = str(question or "").strip()
    if not text:
        return None

    path_match = _FILE_RE.search(text) or _DOCKERFILE_RE.search(text)
    if path_match:
        return {"entity": _clean_entity(path_match.group(1)), "expected_kind": "file", "source": "path"}

    kind_match = _EXPLICIT_KIND_RE.search(text)
    if kind_match:
        raw_kind = kind_match.group(1).lower()
        kind = "config" if raw_kind in {"configuration", "setting", "environment variable", "env var"} else raw_kind
        return {"entity": _clean_entity(kind_match.group(2)), "expected_kind": kind, "source": "explicit_kind"}

    # Upper-case settings named before "configured" are common config queries.
    config_match = re.search(r"\b([A-Z][A-Z0-9_]{2,})\b.*\bconfigured\b", text)
    if config_match:
        return {"entity": config_match.group(1), "expected_kind": "config", "source": "configured_name"}

    artifact_match = re.search(
        r"\b((?:production\s+|staging\s+)?(?:deployment|deploy|configuration|config)\s+file)\b",
        text,
        re.IGNORECASE,
    )
    if artifact_match:
        return {"entity": _clean_entity(artifact_match.group(1)), "expected_kind": "file", "source": "artifact_type"}

    where_match = _WHERE_RE.search(text)
    if where_match:
        entity = _clean_entity(where_match.group(1))
        if _looks_specific(entity):
            return {"entity": entity, "expected_kind": "symbol_or_file", "source": "where"}

    how_match = _HOW_RE.search(text)
    if how_match:
        entity = _clean_entity(how_match.group(1))
        if _looks_specific(entity):
            return {"entity": entity, "expected_kind": "symbol_or_file", "source": "how"}

    # An unknown short phrase has no grounded route; treat the phrase itself as
    # the requested entity instead of silently summarizing the repository.
    if mode == "unknown" and _looks_specific(text):
        return {"entity": _clean_entity(text), "expected_kind": "symbol_or_file", "source": "unknown_phrase"}

    if mode in _BROAD_MODES:
        return None
    return None


def _indexed_files(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in (index.get("files") or []) if item.get("path")]


def _indexed_symbols(evidence_store: Dict[str, Any]) -> List[Dict[str, Any]]:
    symbols: List[Dict[str, Any]] = []
    files = ((evidence_store.get("symbol_index") or {}).get("files") or {})
    for path, scan in files.items():
        for raw in (scan or {}).get("symbols") or []:
            if raw.get("is_definition", True) is False or raw.get("kind") == "import":
                continue
            item = dict(raw)
            item["file_path"] = str(item.get("file_path") or path).replace("\\", "/")
            symbols.append(item)
    return symbols


def _expected_symbol_kinds(expected_kind: str) -> Optional[set[str]]:
    return _KIND_MAP.get(expected_kind)


def _symbol_label(symbol: Dict[str, Any]) -> str:
    name = str(symbol.get("qualname") or symbol.get("name") or "")
    path = str(symbol.get("file_path") or "")
    line = int(symbol.get("line") or 0)
    location = f"{path}:{line}" if line else path
    return f"{symbol.get('kind', 'symbol')} `{name}` in `{location}`"


def _similar_items(
    entity: str,
    expected_kind: str,
    files: List[Dict[str, Any]],
    symbols: List[Dict[str, Any]],
    *,
    exact_symbols: Optional[List[Dict[str, Any]]] = None,
    exact_files: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    def add(kind: str, name: str, path: str, detail: str) -> None:
        key = (kind, f"{name}|{path}".lower())
        if key in seen or len(suggestions) >= 6:
            return
        seen.add(key)
        suggestions.append({"kind": kind, "name": name, "path": path, "detail": detail})

    for symbol in exact_symbols or []:
        add(
            "symbol",
            str(symbol.get("qualname") or symbol.get("name") or ""),
            str(symbol.get("file_path") or ""),
            _symbol_label(symbol),
        )
    for item in exact_files or []:
        path = str(item.get("path") or "")
        add("file", path, path, f"file `{path}`")

    if suggestions:
        return suggestions

    target = _normal(entity)
    allowed = _expected_symbol_kinds(expected_kind)
    symbol_candidates: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        if allowed and str(symbol.get("kind") or "") not in allowed:
            continue
        for value in (symbol.get("name"), symbol.get("qualname")):
            key = _normal(str(value or ""))
            if key:
                symbol_candidates.setdefault(key, symbol)
    file_candidates = {_normal(str(item.get("path") or "")): item for item in files}

    for key in difflib.get_close_matches(target, list(symbol_candidates), n=4, cutoff=0.45):
        symbol = symbol_candidates[key]
        add(
            "symbol",
            str(symbol.get("qualname") or symbol.get("name") or ""),
            str(symbol.get("file_path") or ""),
            _symbol_label(symbol),
        )
    for key in difflib.get_close_matches(target, list(file_candidates), n=4, cutoff=0.35):
        path = str(file_candidates[key].get("path") or "")
        add("file", path, path, f"file `{path}`")
    return suggestions


def resolve_indexed_entity(
    question: str,
    mode: str,
    index: Dict[str, Any],
    evidence_store: Dict[str, Any],
    *,
    node_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a named query entity against indexed paths and definitions."""

    if node_context and node_context.get("path"):
        candidate = {"entity": str(node_context["path"]), "expected_kind": "file", "source": "node_context"}
    else:
        candidate = extract_query_entity(question, mode)
    if candidate is None:
        return None

    entity = candidate["entity"]
    expected_kind = candidate["expected_kind"]
    normalized = _normal(entity)
    files = _indexed_files(index)
    symbols = _indexed_symbols(evidence_store)
    allowed = _expected_symbol_kinds(expected_kind)

    exact_files: List[Dict[str, Any]] = []
    for item in files:
        path = _normal(str(item.get("path") or ""))
        basename = path.rsplit("/", 1)[-1]
        if path == normalized or ("/" not in normalized and basename == normalized):
            if expected_kind == "config" and item.get("role") != "config":
                continue
            exact_files.append(item)

    exact_symbols: List[Dict[str, Any]] = []
    for symbol in symbols:
        kind = str(symbol.get("kind") or "")
        if allowed and kind not in allowed:
            continue
        names = {
            _normal(str(symbol.get("name") or "")),
            _normal(str(symbol.get("qualname") or "")),
        }
        if normalized in names or any(name.endswith("." + normalized) for name in names if name):
            exact_symbols.append(symbol)

    matches: List[Dict[str, Any]] = []
    for item in exact_files:
        matches.append({"kind": "file", "path": item.get("path"), "direct_evidence": f"file `{item.get('path')}` is indexed"})
    for symbol in exact_symbols:
        matches.append({
            "kind": str(symbol.get("kind") or "symbol"),
            "path": symbol.get("file_path"),
            "line": int(symbol.get("line") or 0),
            "name": symbol.get("qualname") or symbol.get("name"),
            "direct_evidence": _symbol_label(symbol),
        })

    # A path match is unique even when that file also defines a same-named
    # symbol. Symbol-only queries require exactly one definition.
    if expected_kind == "file" and len(exact_files) == 1:
        status = "found"
        matches = matches[:1]
    elif len(matches) == 1:
        status = "found"
    elif len(matches) > 1:
        status = "ambiguous"
    else:
        status = "not_found"

    searched = [
        f"Exact indexed file path or basename: {entity} ({len(files)} paths checked)",
        f"Exact indexed symbol name or qualified name: {entity} ({len(symbols)} definitions checked)",
    ]
    if allowed:
        searched.append("Expected symbol kinds: " + ", ".join(sorted(allowed)))

    return {
        **candidate,
        "status": status,
        "matches": matches,
        "searched": searched,
        "similar": _similar_items(
            entity,
            expected_kind,
            files,
            symbols,
            exact_symbols=exact_symbols if status == "ambiguous" else None,
            exact_files=exact_files if status == "ambiguous" else None,
        ),
        "direct_evidence": [item["direct_evidence"] for item in matches if item.get("direct_evidence")],
    }
