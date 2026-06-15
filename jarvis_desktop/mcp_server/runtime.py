"""Local MCP server for Atlas repository intelligence.

The server is intentionally stdio-only: no sockets, no remote transport, and no
write/edit tools. Tool handlers reuse the existing desktop internals and return
compact JSON summaries without source contents, prompts, exports, environment
variables, or secrets.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .. import api, repository_memory as repo_memory
from ..context_pack import build_context_pack_from_state

MCP_PROTOCOL_VERSION = "2024-11-05"
ATLAS_MCP_VERSION = "1.0.0"

_SECRET_KEY_RE = re.compile(
    r"(secret|token|password|passwd|api[_-]?key|authorization|bearer|cookie|session|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|bearer\s+[A-Za-z0-9._-]+|api[_-]?key\s*[:=]\s*[^,\s]+)"
)


def _schema(
    *,
    properties: Dict[str, Any],
    required: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required or [],
    }


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "atlas_scan_repo",
        "description": "Scan a local repository with Atlas and cache read-only repository intelligence for later MCP calls.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Absolute or workspace-relative local repository path."},
                "scope": {"type": "object", "description": "Optional Atlas scan scope.", "additionalProperties": True},
            },
            required=["repo_path"],
        ),
    },
    {
        "name": "atlas_get_codebase_map",
        "description": "Return a compact map of the currently scanned repository.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
            },
        ),
    },
    {
        "name": "atlas_build_context_pack",
        "description": "Build a compact task-scoped context pack from the current scan.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
                "task": {"type": "string", "description": "Natural-language coding task."},
                "max_files": {"type": "integer", "minimum": 1, "maximum": 24, "default": 12},
            },
            required=["task"],
        ),
    },
    {
        "name": "atlas_what_breaks",
        "description": "Run Atlas What Breaks impact analysis for a file/module target in the current scan.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
                "target": {"type": "string", "description": "File path, module path, or supported semantic target."},
                "changed_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alias for `target`: one or more changed file paths. The first is analyzed.",
                },
            },
            required=[],
        ),
    },
    {
        "name": "atlas_plan_change",
        "description": "Build a read-only Atlas Change Plan for the current scan.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
                "request": {"type": "string", "description": "Natural-language change request."},
            },
            required=["request"],
        ),
    },
    {
        "name": "atlas_find_file",
        "description": "Find files in the current scan by path/name terms without returning file contents.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
                "query": {"type": "string", "description": "Path, filename, module, or concept terms."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            required=["query"],
        ),
    },
    {
        "name": "atlas_repo_health",
        "description": "Return scan, graph, trust, and repository-memory health for the current scan.",
        "inputSchema": _schema(
            properties={
                "repo_path": {"type": "string", "description": "Optional path that must match the current scan."},
            },
        ),
    },
]


def _ok(**payload: Any) -> Dict[str, Any]:
    return {"ok": True, **payload}


def _err(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "code": code, "error": message, **extra}


def _norm_path(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def _local_repo_path(path: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    raw = str(path or "").strip()
    if not raw:
        return None, _err("missing_repo_path", "`repo_path` is required.")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        return None, _err("remote_repo_not_allowed", "Atlas MCP only accepts local filesystem paths.")
    full = os.path.abspath(raw)
    if not os.path.isdir(full):
        return None, _err("repo_not_found", "Repository path does not exist or is not a directory.", repo_path=full)
    return full, None


def _current_repo() -> str:
    return os.path.abspath(str(api._STATE.get("path") or ""))


def _scan_ready(repo_path: str = "") -> Optional[Dict[str, Any]]:
    if not api._STATE.get("scan"):
        return _err("requires_scan", "Run `atlas_scan_repo` before using this tool.")
    if repo_path:
        full, err = _local_repo_path(repo_path)
        if err:
            return err
        if full and os.path.abspath(full) != _current_repo():
            return _err(
                "requires_scan",
                "The requested repository is not the active Atlas scan. Run `atlas_scan_repo` for this path first.",
                active_repo=_current_repo(),
                requested_repo=full,
            )
    return None


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _SECRET_KEY_RE.search(key_s):
                out[key_s] = "[REDACTED]"
            else:
                out[key_s] = _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("[REDACTED]", value)
    return value


def _files_from_index(limit: int = 12) -> List[Dict[str, Any]]:
    files = (api._STATE.get("index") or {}).get("files") or []
    out = []
    for item in files[: max(0, limit)]:
        out.append({
            "path": _norm_path(str(item.get("path") or "")),
            "role": item.get("role") or "",
            "size": int(item.get("size") or 0),
        })
    return out


def _compact_summary(limit: int = 12) -> Dict[str, Any]:
    summary = api.current_summary()
    if not summary.get("ok"):
        return summary
    return {
        "ok": True,
        "repo_name": summary.get("repo_name"),
        "repo_path": summary.get("repo_path"),
        "file_count": summary.get("file_count"),
        "module_count": summary.get("module_count"),
        "subsystem_count": summary.get("subsystem_count"),
        "dependency_edges": summary.get("dependency_edges"),
        "graph_health": summary.get("graph_health"),
        "degraded": bool(summary.get("degraded")),
        "language_breakdown": summary.get("language_breakdown") or {},
        "entry_points": (summary.get("entry_points") or [])[:limit],
        "subsystems": (summary.get("subsystems") or [])[:limit],
        "top_hubs": (summary.get("top_hubs") or [])[:limit],
        "top_risks": (summary.get("top_risks") or [])[:limit],
        "explanation": summary.get("explanation"),
    }


def _memory() -> Dict[str, Any]:
    memory = api._STATE.get("repository_memory") or api._STATE.get("_current_memory")
    repo_path = _current_repo()
    if not memory or os.path.abspath(str(memory.get("repo_path") or "")) != repo_path:
        memory = repo_memory.build_memory(dict(api._STATE), generated_by_version="mcp")
    return memory or {}


def _compact_pack(pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": bool(pack.get("ok")),
        "repo_name": pack.get("repo_name"),
        "task": pack.get("task"),
        "confidence": pack.get("confidence"),
        "confidence_score": pack.get("confidence_score"),
        "token_estimate": pack.get("token_estimate"),
        "recommended_files": [
            {
                "path": item.get("path"),
                "score": item.get("score"),
                "role": item.get("role"),
                "subsystem": item.get("subsystem"),
                "reasons": (item.get("reasons") or [])[:4],
            }
            for item in pack.get("recommended_files") or []
        ],
        "related_tests": [
            {
                "path": item.get("path"),
                "score": item.get("score"),
                "reasons": (item.get("reasons") or [])[:3],
            }
            for item in pack.get("related_tests") or []
        ],
        "impacted_subsystems": pack.get("impacted_subsystems") or [],
        "relevant_commands": pack.get("relevant_commands") or [],
        "dependency_notes": pack.get("dependency_notes") or [],
        "excluded_files": pack.get("excluded_files") or [],
        "confidence_reasons": pack.get("confidence_reasons") or [],
    }


def _compact_impact(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "target": result.get("target"),
        "resolved_target": result.get("resolved_target") or result.get("target"),
        "risk_level": result.get("risk_level"),
        "confidence": result.get("confidence"),
        "direct_impact": (result.get("direct_impact") or [])[:25],
        "indirect_impact": (result.get("indirect_impact") or [])[:25],
        "affected_files": (result.get("affected_files") or [])[:40],
        "affected_subsystems": result.get("affected_subsystems") or [],
        "recommended_verification": result.get("recommended_verification") or [],
        "what_may_break": result.get("what_may_break") or [],
        "what_probably_wont_break": result.get("what_probably_wont_break") or [],
        "limitations": result.get("limitations") or [],
    }


def _compact_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result.get("ok"):
        return result
    plan = result.get("plan") or {}
    return {
        "ok": True,
        "request": plan.get("request") or plan.get("goal") or "",
        "intent": plan.get("intent"),
        "confidence": plan.get("confidence"),
        "summary": plan.get("summary") or result.get("summary") or "",
        "files": plan.get("files") or plan.get("target_files") or [],
        "steps": plan.get("steps") or plan.get("plan") or [],
        "tests": plan.get("tests") or plan.get("recommended_tests") or [],
        "risks": plan.get("risks") or plan.get("risk_notes") or [],
        "verification": plan.get("verification") or plan.get("verification_steps") or [],
        "trust_status": result.get("trust_status") or result.get("status"),
    }


def _find_files(query: str, limit: int) -> Dict[str, Any]:
    terms = [t for t in re.split(r"[^A-Za-z0-9_./-]+", (query or "").lower()) if t]
    if not terms:
        return _err("missing_query", "`query` is required.")
    files = (api._STATE.get("index") or {}).get("files") or []
    ranked: List[Tuple[float, Dict[str, Any], List[str]]] = []
    for item in files:
        path = _norm_path(str(item.get("path") or ""))
        p_lower = path.lower()
        base = os.path.basename(p_lower)
        parts = set(re.split(r"[^a-z0-9_]+", p_lower))
        score = 0.0
        reasons: List[str] = []
        for term in terms:
            t = term.strip("./")
            if not t:
                continue
            if p_lower == t or p_lower.endswith("/" + t):
                score += 80
                reasons.append(f"exact path suffix `{term}`")
            elif base == t or base == f"{t}.py":
                score += 60
                reasons.append(f"filename match `{term}`")
            elif t in parts:
                score += 30
                reasons.append(f"path part `{term}`")
            elif t in p_lower:
                score += 14
                reasons.append(f"path contains `{term}`")
        if score:
            ranked.append((score, item, reasons))
    ranked.sort(key=lambda row: (-row[0], _norm_path(str(row[1].get("path") or ""))))
    return _ok(
        query=query,
        matches=[
            {
                "path": _norm_path(str(item.get("path") or "")),
                "role": item.get("role") or "",
                "size": int(item.get("size") or 0),
                "score": round(score, 1),
                "reasons": reasons[:4],
            }
            for score, item, reasons in ranked[:limit]
        ],
    )


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    args = arguments or {}
    try:
        if name == "atlas_scan_repo":
            repo_path, err = _local_repo_path(str(args.get("repo_path") or ""))
            if err:
                return err
            result = api.scan_repository(repo_path, args.get("scope"))
            if not result.get("ok"):
                return _sanitize(result)
            summary = _compact_summary(limit=12)
            return _sanitize(_ok(
                repo_path=repo_path,
                scan={
                    "repo_name": result.get("repo_name"),
                    "file_count": result.get("file_count"),
                    "module_count": result.get("module_count"),
                    "dependency_edges": result.get("dependency_edges"),
                    "graph_health": result.get("graph_health"),
                    "degraded": bool(result.get("degraded")),
                    "cache": result.get("cache") or {},
                },
                codebase_map=summary if summary.get("ok") else None,
            ))

        if name == "atlas_get_codebase_map":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            limit = max(1, min(50, int(args.get("limit") or 12)))
            return _sanitize(_compact_summary(limit=limit))

        if name == "atlas_build_context_pack":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            task = str(args.get("task") or "").strip()
            if not task:
                return _err("missing_task", "`task` is required.")
            max_files = max(1, min(24, int(args.get("max_files") or 12)))
            pack = build_context_pack_from_state(
                _current_repo(),
                task,
                dict(api._STATE),
                memory=_memory(),
                include_snippets=False,
                max_files=max_files,
            )
            return _sanitize(_compact_pack(pack))

        if name == "atlas_what_breaks":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            target = str(args.get("target") or "").strip()
            if not target:
                # Accept `changed_files: [...]` (or `changed_file`) as an alias for `target`.
                changed = args.get("changed_files") or args.get("changed_file")
                if isinstance(changed, str):
                    target = changed.strip()
                elif isinstance(changed, (list, tuple)) and changed:
                    target = str(changed[0]).strip()
            if not target:
                return _err("missing_target", "`target` (or `changed_files`) is required.")
            return _sanitize(_compact_impact(api.change_impact_simulation(target)))

        if name == "atlas_plan_change":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            request = str(args.get("request") or "").strip()
            if not request:
                return _err("missing_request", "`request` is required.")
            return _sanitize(_compact_plan(api.plan_change(request)))

        if name == "atlas_find_file":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            limit = max(1, min(50, int(args.get("limit") or 10)))
            return _sanitize(_find_files(str(args.get("query") or ""), limit))

        if name == "atlas_repo_health":
            err = _scan_ready(str(args.get("repo_path") or ""))
            if err:
                return err
            scan = api._STATE.get("scan") or {}
            trust = api.trust_integrity_status()
            memory = _memory()
            return _sanitize(_ok(
                repo_path=_current_repo(),
                repo_name=scan.get("repo_name"),
                scan={
                    "file_count": scan.get("file_count"),
                    "module_count": scan.get("module_count"),
                    "dependency_edges": scan.get("dependency_edges"),
                    "graph_health": scan.get("graph_health"),
                    "degraded": bool(scan.get("degraded")),
                    "cache": scan.get("cache") or {},
                },
                trust=trust,
                repository_memory={
                    "schema_version": memory.get("schema_version"),
                    "freshness_status": memory.get("freshness_status"),
                    "derivation_confidence": ((memory.get("agent_context") or {}).get("derivation_confidence")),
                },
            ))

        return _err("unknown_tool", f"Unknown Atlas MCP tool: {name}")
    except Exception as exc:
        return _err("tool_failed", f"{type(exc).__name__}: {exc}")


def list_tools() -> Dict[str, Any]:
    return {"tools": TOOLS}


def _mcp_tool_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True)}],
        "isError": not bool(payload.get("ok", True)),
    }


def handle_jsonrpc(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    msg_id = message.get("id")
    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "atlas-local", "version": ATLAS_MCP_VERSION},
                },
            }
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": list_tools()}
        if method == "tools/call":
            params = message.get("params") or {}
            payload = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": _mcp_tool_result(payload)}
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Unsupported MCP method: {method}"},
        }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"},
        }


def _read_messages(stream: Any) -> Iterable[Dict[str, Any]]:
    while True:
        first = stream.readline()
        if not first:
            return
        if isinstance(first, bytes):
            first_text = first.decode("utf-8", errors="replace")
        else:
            first_text = str(first)
        if not first_text.strip():
            continue
        if first_text.lstrip().startswith("{"):
            yield json.loads(first_text)
            continue
        if first_text.lower().startswith("content-length:"):
            length = int(first_text.split(":", 1)[1].strip())
            while True:
                header = stream.readline()
                if isinstance(header, bytes):
                    header_text = header.decode("utf-8", errors="replace")
                else:
                    header_text = str(header)
                if header_text in {"\r\n", "\n", ""}:
                    break
            body = stream.read(length)
            if isinstance(body, bytes):
                body_text = body.decode("utf-8", errors="replace")
            else:
                body_text = str(body)
            yield json.loads(body_text)


def _write_message(stream: Any, message: Dict[str, Any]) -> None:
    # MCP stdio transport is newline-delimited JSON: one JSON-RPC message per line,
    # no embedded newlines. json.dumps with compact separators and no indent never
    # emits a newline, so a single trailing "\n" is a valid frame for real clients
    # (Claude Desktop, Cursor, Codex). The reader (_read_messages) still tolerates
    # legacy Content-Length input for backward compatibility.
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(data)
    stream.write(b"\n")
    stream.flush()


def serve_stdio() -> int:
    for message in _read_messages(sys.stdin.buffer):
        response = handle_jsonrpc(message)
        if response is not None:
            _write_message(sys.stdout.buffer, response)
    return 0


def main() -> int:
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
