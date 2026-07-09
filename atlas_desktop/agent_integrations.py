"""Agent integration helpers for Atlas.

This module owns the product-facing bridge from Atlas repository memory/context
packs to local coding agents. It is intentionally local-only: no network calls,
no source dumps by default, and no writes outside the selected repository or the
Claude Desktop config path unless a caller explicitly opts in.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import product_info
from .context_pack import build_context_pack, build_context_pack_from_state, estimate_tokens

ATLAS_START = "<!-- ATLAS:START -->"
ATLAS_END = "<!-- ATLAS:END -->"
_CLAUDE_CONFIG_NAME = "claude_desktop_config.json"
_CURSOR_CONFIG_NAME = "mcp.json"
_CODEX_CONFIG_NAME = "config.toml"

_TARGET_LABELS = {
    "claude": "Claude",
    "cursor": "Cursor",
    "codex": "Codex",
}

_TARGET_PREAMBLES = {
    "claude": (
        "Use this Atlas context as local repository intelligence. Read the listed "
        "files when detail is needed; do not explore the whole repository first."
    ),
    "cursor": (
        "Cursor workspace context from Atlas. Prefer these files, commands, risks, "
        "and constraints before broad search."
    ),
    "codex": (
        "Codex-ready Atlas context. Treat this as a compact task brief: selected "
        "files, why they matter, commands, risks, and verification steps."
    ),
}

_SECRET_VALUE_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|bearer\s+[A-Za-z0-9._-]+|"
    r"api[_-]?key\s*[:=]\s*[^,\s]+|authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]+)"
)


def _redact_text(text: str) -> str:
    return _SECRET_VALUE_RE.sub("[REDACTED]", str(text or ""))


def _target(value: str) -> str:
    t = (value or "claude").strip().lower()
    return t if t in _TARGET_LABELS else "claude"


def _repo_path_from_state(state: Dict[str, Any]) -> str:
    return os.path.abspath(str(state.get("path") or ((state.get("scan") or {}).get("repo_path") or "")))


def _memory_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("repository_memory") or state.get("_current_memory") or {}


def _commands(pack: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for item in pack.get("relevant_commands") or []:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    if not out:
        out.append("UNKNOWN - Atlas did not find a confident command.")
    return out


def _selected_paths(pack: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for group in ("recommended_files", "related_tests"):
        for item in pack.get(group) or []:
            path = str(item.get("path") or "").strip()
            if path and path not in paths:
                paths.append(path)
    return paths


def _verification_plan(pack: Dict[str, Any]) -> List[str]:
    plan: List[str] = []
    for cmd in _commands(pack):
        lowered = cmd.lower()
        if cmd != "UNKNOWN - Atlas did not find a confident command." and "no reliable" not in lowered and "unknown" not in lowered:
            plan.append(f"Run `{cmd}` if it is relevant to the changed files.")
    if not plan:
        plan.append("Atlas did not find a confident command; run the nearest package or repository tests manually.")
    tests = [str(item.get("path")) for item in pack.get("related_tests") or [] if item.get("path")]
    if tests:
        plan.append("Inspect or run the related tests listed in the pack.")
    plan.append("Manually verify behavior around the selected files before shipping.")
    return plan


def render_task_export(pack: Dict[str, Any], *, target: str) -> str:
    """Render a task-scoped export without file bodies or snippets."""
    target = _target(target)
    label = _TARGET_LABELS[target]
    lines: List[str] = [
        f"# Atlas Context for {label}",
        "",
        _TARGET_PREAMBLES[target],
        "",
        "## Task",
        _redact_text(str(pack.get("task") or "").strip()) or "UNKNOWN",
        "",
        "## Selected Files",
    ]
    recs = pack.get("recommended_files") or []
    if recs:
        for item in recs:
            reasons = "; ".join((item.get("reasons") or ["selected by Atlas ranking"])[:3])
            lines.append(f"- `{item.get('path')}`: {reasons}")
    else:
        lines.append("- UNKNOWN - Atlas could not identify relevant files with enough confidence.")

    lines.extend(["", "## Related Tests"])
    tests = pack.get("related_tests") or []
    if tests:
        for item in tests:
            reasons = "; ".join((item.get("reasons") or ["test proximity"])[:2])
            lines.append(f"- `{item.get('path')}`: {reasons}")
    else:
        lines.append("- UNKNOWN - no close test files identified.")

    lines.extend(["", "## Impacted Subsystems"])
    subs = pack.get("impacted_subsystems") or []
    lines.append(", ".join(f"`{s}`" for s in subs) if subs else "UNKNOWN")

    lines.extend(["", "## Commands"])
    for cmd in _commands(pack):
        lines.append(f"- {cmd}")

    lines.extend(["", "## Dependency Notes"])
    notes = pack.get("dependency_notes") or []
    if notes:
        lines.extend(f"- {note}" for note in notes[:8])
    else:
        lines.append("- No selected-file dependency links identified.")

    lines.extend(["", "## Constraints"])
    constraints = pack.get("known_constraints") or []
    if constraints:
        lines.extend(f"- {item}" for item in constraints[:8])
    else:
        lines.append("- No repository-memory constraints identified.")

    lines.extend(["", "## Verification Plan"])
    lines.extend(f"- {item}" for item in _verification_plan(pack))

    lines.extend(["", "## Excluded Files"])
    excluded = pack.get("excluded_files") or []
    if excluded:
        for item in excluded[:10]:
            lines.append(f"- `{item.get('path')}`: {item.get('reason') or 'likely irrelevant'}")
    else:
        lines.append("- No notable exclusions.")

    lines.extend([
        "",
        "## Confidence",
        f"{pack.get('confidence', 'LOW')} ({pack.get('confidence_score', 0)}/100)",
    ])
    for reason in pack.get("confidence_reasons") or []:
        lines.append(f"- {reason}")

    lines.extend([
        "",
        "## Exact Prompt",
        f"Use the Atlas context above to work on: {_redact_text(str(pack.get('task') or '').strip()) or 'the requested task'}. "
        "Start with the selected files. Keep changes scoped. Run the verification plan. "
        "If confidence is LOW or a needed file is missing, say so before editing.",
        "",
        "## Privacy",
        "Atlas included the redacted task text above and did not include source file bodies, secrets, exports, absolute repository paths, or environment files in this packet.",
    ])
    return "\n".join(lines).strip() + "\n"


def export_for_state(
    state: Dict[str, Any],
    *,
    target: str,
    task: str,
    max_files: int = 12,
) -> Dict[str, Any]:
    repo_path = _repo_path_from_state(state)
    if not repo_path or not state.get("scan"):
        return {"ok": False, "code": "requires_scan", "error": "Scan a repository before exporting agent context."}
    task = (task or "").strip()
    if not task:
        return {"ok": False, "code": "missing_task", "error": "Task is required for task-scoped agent export."}
    pack = build_context_pack_from_state(
        repo_path,
        task,
        dict(state),
        memory=_memory_from_state(state),
        include_snippets=False,
        max_files=max(1, min(24, int(max_files or 12))),
    )
    if not pack.get("ok"):
        return pack
    target = _target(target)
    text = _redact_text(render_task_export(pack, target=target))
    return {
        "ok": True,
        "target": target,
        "task": _redact_text(task),
        "repo_name": pack.get("repo_name"),
        "confidence": pack.get("confidence"),
        "confidence_score": pack.get("confidence_score"),
        "estimated_tokens": estimate_tokens(text),
        "selected_files": _selected_paths(pack),
        "text": text,
        "context_pack": {
            "recommended_files": pack.get("recommended_files") or [],
            "related_tests": pack.get("related_tests") or [],
            "impacted_subsystems": pack.get("impacted_subsystems") or [],
            "relevant_commands": pack.get("relevant_commands") or [],
            "excluded_files": pack.get("excluded_files") or [],
        },
    }


def export_for_repo(
    repo_path: str,
    *,
    target: str,
    task: str,
    max_files: int = 12,
) -> Dict[str, Any]:
    repo_path = os.path.abspath(str(repo_path or ""))
    if not os.path.isdir(repo_path):
        return {"ok": False, "code": "repo_not_found", "error": "Repository path does not exist.", "repo_path": repo_path}
    task = (task or "").strip()
    if not task:
        return {"ok": False, "code": "missing_task", "error": "Task is required."}
    pack = build_context_pack(repo_path, task, include_snippets=False, max_files=max(1, min(24, int(max_files or 12))))
    if not pack.get("ok"):
        return pack
    target = _target(target)
    text = _redact_text(render_task_export(pack, target=target))
    return {
        "ok": True,
        "target": target,
        "task": _redact_text(task),
        "repo_path": repo_path,
        "repo_name": pack.get("repo_name"),
        "confidence": pack.get("confidence"),
        "confidence_score": pack.get("confidence_score"),
        "estimated_tokens": estimate_tokens(text),
        "selected_files": _selected_paths(pack),
        "text": text,
    }


def _platform_default_claude_config_path() -> str:
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            "Claude",
            _CLAUDE_CONFIG_NAME,
        )
    if sys.platform.startswith("linux"):
        return os.path.join(os.path.expanduser("~"), ".config", "Claude", _CLAUDE_CONFIG_NAME)
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.join(appdata, "Claude", _CLAUDE_CONFIG_NAME)
    return os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Claude", _CLAUDE_CONFIG_NAME)


def discover_claude_desktop_config_paths() -> List[Dict[str, Any]]:
    """Return known Claude Desktop config locations (APPDATA, Store, Anthropic paths)."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def add(path: str, source: str) -> None:
        resolved = os.path.abspath(path)
        if resolved in seen:
            if source != "default":
                for item in out:
                    if item["path"] == resolved and item["source"] == "default":
                        item["source"] = source
            return
        seen.add(resolved)
        parent = os.path.dirname(resolved)
        out.append(
            {
                "path": resolved,
                "source": source,
                "exists": os.path.isfile(resolved),
                "parent_exists": os.path.isdir(parent),
            }
        )

    add(_platform_default_claude_config_path(), "default")

    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        add(os.path.join(appdata, "Claude", _CLAUDE_CONFIG_NAME), "appdata_roaming")

    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        add(os.path.join(local, "Claude", _CLAUDE_CONFIG_NAME), "localappdata_claude")
        add(os.path.join(local, "AnthropicClaude", _CLAUDE_CONFIG_NAME), "localappdata_anthropic")
        packages = os.path.join(local, "Packages")
        if os.path.isdir(packages):
            for entry in os.scandir(packages):
                if not entry.is_dir():
                    continue
                low = entry.name.lower()
                if "claude" not in low and "anthropic" not in low:
                    continue
                for rel in (
                    os.path.join("LocalCache", "Roaming", "Claude", _CLAUDE_CONFIG_NAME),
                    os.path.join("LocalState", "Claude", _CLAUDE_CONFIG_NAME),
                    os.path.join("Roaming", "Claude", _CLAUDE_CONFIG_NAME),
                ):
                    add(os.path.join(entry.path, rel), f"microsoft_store:{entry.name}")

    return out


def claude_desktop_config_path() -> str:
    for item in discover_claude_desktop_config_paths():
        if item.get("exists"):
            return str(item["path"])
    return _platform_default_claude_config_path()


def _claude_config_source_for_path(path: str) -> str:
    target = os.path.abspath(path)
    for item in discover_claude_desktop_config_paths():
        if os.path.abspath(str(item.get("path") or "")) == target:
            return str(item.get("source") or "discovered")
    return "default"


def atlas_executable_path() -> str:
    """Return the installed Atlas.exe path when available (never hardcoded)."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)

    override = os.environ.get("ATLAS_EXE_PATH", "").strip()
    if override and os.path.isfile(override):
        return os.path.abspath(override)

    candidates: List[str] = []
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        candidates.append(os.path.join(local, "Programs", "Atlas", "Atlas.exe"))
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name, "").strip()
        if base:
            candidates.append(os.path.join(base, "Atlas", "Atlas.exe"))

    exe_name = os.path.basename(sys.executable).lower()
    if exe_name == "atlas.exe" and os.path.isfile(sys.executable):
        candidates.insert(0, sys.executable)

    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    bundled = os.path.join(root, "dist", "Atlas", "Atlas.exe")
    if os.path.isfile(bundled):
        return os.path.abspath(bundled)

    return os.path.abspath(sys.executable)


def _atlas_mcp_command() -> Tuple[str, List[str]]:
    exe = atlas_executable_path()
    if exe.lower().endswith("atlas.exe"):
        return exe, ["--mcp"]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    runner = os.path.join(root, "run_atlas.py")
    return os.path.abspath(sys.executable), [runner, "--mcp"]


def mcp_snippet(server_name: str = "atlas") -> Dict[str, Any]:
    command, args = _atlas_mcp_command()
    return {
        "mcpServers": {
            server_name: {
                "command": command,
                "args": args,
            }
        }
    }


def claude_mcp_snippet(server_name: str = "atlas") -> Dict[str, Any]:
    return mcp_snippet(server_name)


def _backup_config_file(path: str) -> Optional[str]:
    target = Path(path)
    if not target.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.atlas-backup-{stamp}")
    shutil.copy2(target, backup)
    return str(backup)


def _validate_mcp_config_data(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return "Config root is not a JSON object."
    servers = data.get("mcpServers")
    if servers is None:
        return None
    if not isinstance(servers, dict):
        return "`mcpServers` is not a JSON object."
    return None


def _write_mcp_servers_config(
    path: str,
    *,
    server_name: str = "atlas",
    client_label: str,
) -> Dict[str, Any]:
    target = Path(path)
    data: Dict[str, Any] = {}
    backup_path: Optional[str] = None

    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            snippet = mcp_snippet(server_name)
            return {
                "ok": False,
                "code": "invalid_config",
                "error": f"{client_label} config is not valid JSON: {exc}",
                "config_path": path,
                "fallback_json": json.dumps(snippet, indent=2),
            }
        invalid = _validate_mcp_config_data(data)
        if invalid:
            snippet = mcp_snippet(server_name)
            return {
                "ok": False,
                "code": "invalid_config",
                "error": invalid,
                "config_path": path,
                "fallback_json": json.dumps(snippet, indent=2),
            }
        try:
            backup_path = _backup_config_file(path)
        except OSError as exc:
            snippet = mcp_snippet(server_name)
            return {
                "ok": False,
                "code": "backup_failed",
                "error": f"Could not back up existing config: {exc}",
                "config_path": path,
                "fallback_json": json.dumps(snippet, indent=2),
            }

    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        snippet = mcp_snippet(server_name)
        return {
            "ok": False,
            "code": "invalid_config",
            "error": "`mcpServers` is not a JSON object.",
            "config_path": path,
            "fallback_json": json.dumps(snippet, indent=2),
        }

    preserved = sorted(str(k) for k in servers.keys() if k != server_name)
    servers[server_name] = mcp_snippet(server_name)["mcpServers"][server_name]
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(data, indent=2) + "\n"
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(rendered, encoding="utf-8")
        try:
            json.loads(tmp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "code": "validation_failed",
                "error": f"Written JSON failed validation: {exc}",
                "config_path": path,
                "fallback_json": json.dumps(mcp_snippet(server_name), indent=2),
            }
        try:
            os.replace(tmp, target)
        except PermissionError:
            target.write_text(rendered, encoding="utf-8")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError as exc:
        snippet = mcp_snippet(server_name)
        return {
            "ok": False,
            "code": "write_failed",
            "error": str(exc),
            "config_path": path,
            "fallback_json": json.dumps(snippet, indent=2),
        }

    return {
        "ok": True,
        "config_path": path,
        "backup_path": backup_path,
        "server_name": server_name,
        "preserved_server_names": preserved,
        "atlas_configured": True,
        "executable_path": atlas_executable_path(),
    }


def _platform_default_cursor_config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".cursor", _CURSOR_CONFIG_NAME)


def discover_cursor_mcp_config_paths() -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def add(path: str, source: str) -> None:
        resolved = os.path.abspath(path)
        if resolved in seen:
            return
        seen.add(resolved)
        parent = os.path.dirname(resolved)
        out.append(
            {
                "path": resolved,
                "source": source,
                "exists": os.path.isfile(resolved),
                "parent_exists": os.path.isdir(parent),
            }
        )

    add(_platform_default_cursor_config_path(), "default")
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        add(os.path.join(appdata, "Cursor", "User", "globalStorage", "cursor.mcp", _CURSOR_CONFIG_NAME), "appdata_cursor_mcp")
    return out


def cursor_config_path() -> str:
    for item in discover_cursor_mcp_config_paths():
        if item.get("exists"):
            return str(item["path"])
    return _platform_default_cursor_config_path()


def _cursor_config_source_for_path(path: str) -> str:
    target = os.path.abspath(path)
    for item in discover_cursor_mcp_config_paths():
        if os.path.abspath(str(item.get("path") or "")) == target:
            return str(item.get("source") or "discovered")
    return "default"


def cursor_config_status() -> Dict[str, Any]:
    path = cursor_config_path()
    discovered = discover_cursor_mcp_config_paths()
    snippet = mcp_snippet()
    exists = os.path.exists(path)
    server_names: List[str] = []
    atlas_configured = False
    invalid = False
    if exists:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
            servers = data.get("mcpServers") if isinstance(data, dict) else {}
            if isinstance(servers, dict):
                server_names = sorted(str(k) for k in servers.keys())
                atlas_configured = "atlas" in servers
        except (OSError, json.JSONDecodeError):
            invalid = True
    return {
        "ok": True,
        "config_path": path,
        "config_source": _cursor_config_source_for_path(path),
        "discovered_paths": discovered,
        "exists": exists,
        "invalid_json": invalid,
        "atlas_configured": atlas_configured,
        "existing_server_names": server_names,
        "snippet": snippet,
        "copyable_json": json.dumps(snippet, indent=2),
        "can_auto_write": not invalid,
        "requires_confirmation": True,
    }


def write_cursor_config(*, confirm: bool = False, server_name: str = "atlas") -> Dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "code": "confirmation_required",
            "error": "Atlas will only write Cursor MCP config after explicit confirmation.",
        }
    result = _write_mcp_servers_config(
        cursor_config_path(),
        server_name=server_name,
        client_label="Cursor",
    )
    if result.get("ok"):
        result["message"] = (
            "Atlas was added to Cursor. Restart Cursor, then open Settings → MCP and confirm Atlas is connected."
        )
    return result


def claude_config_status() -> Dict[str, Any]:
    path = claude_desktop_config_path()
    discovered = discover_claude_desktop_config_paths()
    snippet = claude_mcp_snippet()
    exists = os.path.exists(path)
    server_names: List[str] = []
    atlas_configured = False
    invalid = False
    if exists:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
            servers = data.get("mcpServers") if isinstance(data, dict) else {}
            if isinstance(servers, dict):
                server_names = sorted(str(k) for k in servers.keys())
                atlas_configured = "atlas" in servers
        except (OSError, json.JSONDecodeError):
            invalid = True
    return {
        "ok": True,
        "config_path": path,
        "config_source": _claude_config_source_for_path(path),
        "discovered_paths": discovered,
        "exists": exists,
        "invalid_json": invalid,
        "atlas_configured": atlas_configured,
        "existing_server_names": server_names,
        "snippet": snippet,
        "copyable_json": json.dumps(snippet, indent=2),
        "can_auto_write": not invalid,
        "requires_confirmation": True,
    }


def write_claude_config(*, confirm: bool = False, server_name: str = "atlas") -> Dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "code": "confirmation_required",
            "error": "Atlas will only write Claude Desktop config after explicit confirmation.",
        }
    result = _write_mcp_servers_config(
        claude_desktop_config_path(),
        server_name=server_name,
        client_label="Claude Desktop",
    )
    if result.get("ok"):
        result["message"] = (
            "Atlas was added to Claude Desktop. Restart Claude Desktop, then confirm Atlas appears in MCP settings."
        )
    return result


def _toml_single_quoted(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _toml_string_array(values: List[str]) -> str:
    return "[" + ", ".join(_toml_single_quoted(v) for v in values) + "]"


def _platform_default_codex_config_path() -> str:
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        return os.path.join(os.path.abspath(codex_home), _CODEX_CONFIG_NAME)
    return os.path.join(os.path.expanduser("~"), ".codex", _CODEX_CONFIG_NAME)


def discover_codex_config_paths() -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def add(path: str, source: str) -> None:
        resolved = os.path.abspath(path)
        if resolved in seen:
            return
        seen.add(resolved)
        parent = os.path.dirname(resolved)
        out.append(
            {
                "path": resolved,
                "source": source,
                "exists": os.path.isfile(resolved),
                "parent_exists": os.path.isdir(parent),
            }
        )

    add(_platform_default_codex_config_path(), "default")
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        add(os.path.join(local, "OpenAI", "Codex", _CODEX_CONFIG_NAME), "localappdata_openai_codex")
    return out


def codex_config_path() -> str:
    for item in discover_codex_config_paths():
        if item.get("exists"):
            return str(item["path"])
    return _platform_default_codex_config_path()


def _codex_config_source_for_path(path: str) -> str:
    target = os.path.abspath(path)
    for item in discover_codex_config_paths():
        if os.path.abspath(str(item.get("path") or "")) == target:
            return str(item.get("source") or "discovered")
    return "default"


def _load_codex_config(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    target = Path(path)
    if not target.is_file():
        return {}, None
    try:
        return tomllib.loads(target.read_text(encoding="utf-8")), None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, str(exc)


def _mcp_launch_entry() -> Dict[str, Any]:
    command, args = _atlas_mcp_command()
    entry: Dict[str, Any] = {"command": command, "args": list(args), "enabled": True}
    if not command.lower().endswith("atlas.exe"):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        entry["cwd"] = root
    return entry


def _render_codex_mcp_server_block(server_name: str = "atlas") -> str:
    entry = _mcp_launch_entry()
    lines = [
        f"[mcp_servers.{server_name}]",
        f"command = {_toml_single_quoted(str(entry['command']))}",
        f"args = {_toml_string_array([str(v) for v in entry.get('args') or []])}",
    ]
    cwd = entry.get("cwd")
    if cwd:
        lines.append(f"cwd = {_toml_single_quoted(str(cwd))}")
    lines.append("enabled = true")
    return "\n".join(lines)


def _remove_codex_mcp_server_sections(text: str, server_name: str) -> str:
    prefix = f"mcp_servers.{server_name}"
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            header = stripped[1:-1].strip()
            if header == prefix or header.startswith(prefix + "."):
                skip = True
                continue
            skip = False
        if not skip:
            out.append(line)
    return "".join(out).rstrip()


def _codex_server_names(data: Dict[str, Any]) -> List[str]:
    servers = data.get("mcp_servers") if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        return []
    return sorted(str(k) for k in servers.keys())


def _codex_atlas_configured(data: Dict[str, Any], server_name: str = "atlas") -> bool:
    servers = data.get("mcp_servers") if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        return False
    entry = servers.get(server_name)
    return isinstance(entry, dict) and bool(entry.get("command"))


def codex_config_status() -> Dict[str, Any]:
    path = codex_config_path()
    discovered = discover_codex_config_paths()
    entry = _mcp_launch_entry()
    exists = os.path.exists(path)
    server_names: List[str] = []
    atlas_configured = False
    invalid = False
    parse_error = ""
    data, err = _load_codex_config(path) if exists else ({}, None)
    if err:
        invalid = True
        parse_error = err
    elif isinstance(data, dict):
        server_names = _codex_server_names(data)
        atlas_configured = _codex_atlas_configured(data)
    snippet_block = _render_codex_mcp_server_block()
    return {
        "ok": True,
        "config_path": path,
        "config_source": _codex_config_source_for_path(path),
        "discovered_paths": discovered,
        "exists": exists,
        "invalid_toml": invalid,
        "parse_error": parse_error,
        "atlas_configured": atlas_configured,
        "existing_server_names": server_names,
        "snippet": entry,
        "copyable_toml": snippet_block,
        "can_auto_write": not invalid,
        "requires_confirmation": True,
        "availability": "experimental",
    }


def write_codex_config(*, confirm: bool = False, server_name: str = "atlas") -> Dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "code": "confirmation_required",
            "error": "Atlas will only write Codex MCP config after explicit confirmation.",
        }
    path = codex_config_path()
    target = Path(path)
    backup_path: Optional[str] = None
    existing = ""
    if target.is_file():
        try:
            existing = target.read_text(encoding="utf-8")
        except OSError as exc:
            return {
                "ok": False,
                "code": "read_failed",
                "error": str(exc),
                "config_path": path,
                "fallback_toml": _render_codex_mcp_server_block(server_name),
            }
        data, err = _load_codex_config(path)
        if err:
            return {
                "ok": False,
                "code": "invalid_config",
                "error": f"Codex config is not valid TOML: {err}",
                "config_path": path,
                "fallback_toml": _render_codex_mcp_server_block(server_name),
            }
        try:
            backup_path = _backup_config_file(path)
        except OSError as exc:
            return {
                "ok": False,
                "code": "backup_failed",
                "error": f"Could not back up existing config: {exc}",
                "config_path": path,
                "fallback_toml": _render_codex_mcp_server_block(server_name),
            }
    preserved = []
    if existing:
        data, _ = _load_codex_config(path)
        if isinstance(data, dict):
            preserved = [name for name in _codex_server_names(data) if name != server_name]

    block = _render_codex_mcp_server_block(server_name)
    merged = _remove_codex_mcp_server_sections(existing, server_name)
    rendered = (merged.rstrip() + "\n\n" + block + "\n") if merged.strip() else (block + "\n")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(rendered, encoding="utf-8")
        parsed, err = _load_codex_config(str(tmp))
        if err:
            return {
                "ok": False,
                "code": "validation_failed",
                "error": f"Written TOML failed validation: {err}",
                "config_path": path,
                "fallback_toml": block,
            }
        if not isinstance(parsed, dict) or not _codex_atlas_configured(parsed, server_name):
            return {
                "ok": False,
                "code": "validation_failed",
                "error": "Written TOML did not contain a valid mcp_servers.atlas entry.",
                "config_path": path,
                "fallback_toml": block,
            }
        try:
            os.replace(tmp, target)
        except PermissionError:
            target.write_text(rendered, encoding="utf-8")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError as exc:
        return {
            "ok": False,
            "code": "write_failed",
            "error": str(exc),
            "config_path": path,
            "fallback_toml": block,
        }

    return {
        "ok": True,
        "config_path": path,
        "backup_path": backup_path,
        "server_name": server_name,
        "preserved_server_names": preserved,
        "atlas_configured": True,
        "executable_path": atlas_executable_path(),
        "message": "Codex connected. Restart Codex to use Atlas.",
    }


def mcp_setup_status() -> Dict[str, Any]:
    cursor = cursor_config_status()
    claude = claude_config_status()
    codex = codex_config_status()
    command, args = _atlas_mcp_command()
    return {
        "ok": True,
        "executable_path": atlas_executable_path(),
        "executable_exists": os.path.isfile(atlas_executable_path()),
        "mcp_command": command,
        "mcp_args": args,
        "snippet": mcp_snippet(),
        "copyable_json": json.dumps(mcp_snippet(), indent=2),
        "cursor": cursor,
        "claude": claude,
        "codex": codex,
    }


def _exe_help_contains_mcp(exe_path: str) -> Dict[str, Any]:
    if not os.path.isfile(exe_path):
        return {"ok": False, "detail": f"Missing executable: {exe_path}"}
    try:
        proc = subprocess.run(
            [exe_path, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
        if "unrecognized arguments" in combined.lower():
            return {"ok": False, "detail": combined.strip()[:300]}
        ok = "--mcp" in combined
        return {"ok": ok, "detail": "help lists --mcp" if ok else combined.strip()[:300]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}


def _exe_mcp_starts_without_argparse_error(exe_path: str) -> Dict[str, Any]:
    if not os.path.isfile(exe_path):
        return {"ok": False, "detail": f"Missing executable: {exe_path}"}
    proc: Optional[subprocess.Popen[str]] = None
    try:
        proc = subprocess.Popen(
            [exe_path, "--mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.8)
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else "")[:400]
            out = (proc.stdout.read() if proc.stdout else "")[:200]
            combined = f"{out}\n{err}".strip()
            if "unrecognized arguments" in combined.lower():
                return {"ok": False, "detail": combined[:300]}
            return {"ok": False, "detail": combined[:300] or f"exit={proc.returncode}"}
        return {"ok": True, "detail": "MCP process stayed alive (stdio ready)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def run_mcp_diagnostics() -> Dict[str, Any]:
    exe = atlas_executable_path()
    cursor = cursor_config_status()
    claude = claude_config_status()
    codex = codex_config_status()
    snippet = mcp_snippet()
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})

    add("Atlas executable path resolved", bool(exe), exe)
    add("Atlas.exe exists", os.path.isfile(exe), exe)
    help_check = _exe_help_contains_mcp(exe)
    add("Atlas.exe --help contains --mcp", help_check["ok"], help_check.get("detail", ""))
    start_check = _exe_mcp_starts_without_argparse_error(exe)
    add("Atlas.exe --mcp starts without argparse error", start_check["ok"], start_check.get("detail", ""))

    snippet_ok = False
    snippet_detail = ""
    try:
        json.loads(json.dumps(snippet))
        entry = snippet["mcpServers"]["atlas"]
        snippet_ok = bool(entry.get("command")) and entry.get("args") == ["--mcp"]
        snippet_detail = json.dumps(entry)
    except Exception as exc:  # noqa: BLE001
        snippet_detail = f"{type(exc).__name__}: {exc}"
    add("MCP config JSON is valid", snippet_ok, snippet_detail)

    if cursor.get("atlas_configured"):
        add("Cursor MCP config exists", cursor.get("exists"), cursor.get("config_path", ""))
        add("Cursor MCP config JSON valid", not cursor.get("invalid_json"), cursor.get("config_path", ""))
    else:
        add("Cursor MCP config (optional until connected)", True, "Not configured yet")

    if claude.get("atlas_configured"):
        add("Claude Desktop MCP config exists", claude.get("exists"), claude.get("config_path", ""))
        add("Claude Desktop MCP config JSON valid", not claude.get("invalid_json"), claude.get("config_path", ""))
    else:
        add("Claude Desktop MCP config (optional until connected)", True, "Not configured yet")

    if codex.get("atlas_configured"):
        add("Codex MCP config exists", codex.get("exists"), codex.get("config_path", ""))
        add("Codex MCP config TOML valid", not codex.get("invalid_toml"), codex.get("config_path", ""))
    else:
        add("Codex MCP config (optional until connected)", True, "Not configured yet")

    runtime = test_mcp_runtime()
    add("Atlas MCP runtime loads tools", runtime.get("ok"), runtime.get("error") or f"{runtime.get('tool_count', 0)} tools")

    passed = all(item["ok"] for item in checks)
    return {
        "ok": passed,
        "passed": passed,
        "executable_path": exe,
        "checks": checks,
        "cursor_config_path": cursor.get("config_path"),
        "claude_config_path": claude.get("config_path"),
        "codex_config_path": codex.get("config_path"),
        "copyable_json": json.dumps(snippet, indent=2),
        "copyable_codex_toml": codex.get("copyable_toml"),
        "runtime": runtime,
    }


def test_mcp_runtime() -> Dict[str, Any]:
    try:
        from . import mcp_server

        tools = [tool.get("name") for tool in (mcp_server.list_tools().get("tools") or [])]
        return {
            "ok": True,
            "tool_count": len(tools),
            "tools": tools,
            "config": claude_mcp_snippet(),
        }
    except Exception as exc:  # noqa: BLE001 - product-facing diagnostic
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "config": claude_mcp_snippet()}


def _replace_managed_block(existing: str, managed: str) -> str:
    block = f"{ATLAS_START}\n{managed.strip()}\n{ATLAS_END}"
    if ATLAS_START in existing and ATLAS_END in existing:
        before, rest = existing.split(ATLAS_START, 1)
        _old, after = rest.split(ATLAS_END, 1)
        return before.rstrip() + "\n\n" + block + "\n" + after.lstrip()
    return (existing.rstrip() + "\n\n" if existing.strip() else "") + block + "\n"


def write_cursor_rule(repo_path: str, task: str = "", target: str = "cursor") -> Dict[str, Any]:
    repo = Path(os.path.abspath(str(repo_path or "")))
    if not repo.is_dir():
        return {"ok": False, "code": "repo_not_found", "error": "Repository path does not exist.", "repo_path": str(repo)}
    if task.strip():
        export = export_for_repo(str(repo), target=target, task=task, max_files=12)
        if not export.get("ok"):
            return export
        managed = export["text"]
    else:
        managed = (
            "# Atlas-managed Cursor context\n\n"
            "Atlas has analyzed this repository. Use Atlas exports or MCP tools for task-scoped files, risks, tests, and commands.\n"
        )
    path = repo / ".cursor" / "rules" / "atlas.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(_replace_managed_block(existing, managed), encoding="utf-8")
    return {"ok": True, "path": str(path), "managed_markers": [ATLAS_START, ATLAS_END]}


def write_claude_managed_block(repo_path: str, task: str = "") -> Dict[str, Any]:
    repo = Path(os.path.abspath(str(repo_path or "")))
    if not repo.is_dir():
        return {"ok": False, "code": "repo_not_found", "error": "Repository path does not exist.", "repo_path": str(repo)}
    if task.strip():
        export = export_for_repo(str(repo), target="claude", task=task, max_files=12)
        if not export.get("ok"):
            return export
        managed = export["text"]
    else:
        managed = (
            "# Atlas-managed Claude Code notes\n\n"
            "See AGENTS.md for repository facts. Use Atlas task exports or MCP tools for selected files, impact analysis, and verification plans.\n"
        )
    path = repo / "CLAUDE.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(_replace_managed_block(existing, managed), encoding="utf-8")
    return {"ok": True, "path": str(path), "managed_markers": [ATLAS_START, ATLAS_END]}


def about_payload() -> Dict[str, Any]:
    return {
        "ok": True,
        **product_info.version_info(),
        "claude_config_path": claude_desktop_config_path(),
        "mcp": test_mcp_runtime(),
    }
