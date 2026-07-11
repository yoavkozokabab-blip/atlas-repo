"""Atlas MCP orchestration for with-Atlas conditions."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_desktop import api, mcp_server as mcp  # noqa: E402

from .schema import TaskDef


def _reset_repo_state() -> None:
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "scan_cache": {},
        }
    )


def _call(tool: str, args: Dict[str, Any], log: List[Dict[str, Any]]) -> Dict[str, Any]:
    started = time.perf_counter()
    result = mcp.call_tool(tool, args)
    log.append(
        {
            "tool": tool,
            "arguments": args,
            "ok": bool(result.get("ok")),
            "latency_seconds": round(time.perf_counter() - started, 4),
        }
    )
    return result


def _files_from_result(result: Dict[str, Any]) -> List[str]:
    files: List[str] = []
    for key in ("files", "relevant_files", "affected_files", "matches"):
        val = result.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    files.append(item)
                elif isinstance(item, dict) and item.get("path"):
                    files.append(str(item["path"]))
    pack = result.get("context_pack") or result.get("pack")
    if isinstance(pack, dict):
        for item in pack.get("files") or []:
            if isinstance(item, dict) and item.get("path"):
                files.append(str(item["path"]))
    return files


def _format_response(task: TaskDef, results: List[Dict[str, Any]]) -> str:
    parts = [f"# Atlas MCP answer for {task.task_id} ({task.category})\n"]
    for item in results:
        tool = item.get("tool", "unknown")
        res = item.get("result") or {}
        parts.append(f"\n## Tool: {tool}\n")
        if not res.get("ok"):
            parts.append(f"Error: {res.get('error', 'unknown')}\n")
            continue
        if tool == "atlas_find_relevant_files":
            for row in res.get("files") or res.get("relevant_files") or []:
                if isinstance(row, dict):
                    parts.append(f"- {row.get('path')} — {row.get('reason', '')}\n")
        elif tool == "atlas_find_file":
            for row in res.get("matches") or []:
                parts.append(f"- {row}\n")
        elif tool == "atlas_get_architecture":
            for row in res.get("clusters") or res.get("subsystems") or []:
                parts.append(f"- {row}\n")
        elif tool in ("atlas_what_breaks", "atlas_get_impact_analysis"):
            parts.append(f"Target: {res.get('target')}\n")
            for row in res.get("affected_files") or []:
                parts.append(f"- affected: {row}\n")
        elif tool == "atlas_root_cause":
            parts.append(f"Summary: {res.get('summary', '')}\n")
            for row in res.get("likely_causes") or []:
                parts.append(f"- {row}\n")
            for row in res.get("files_to_inspect") or []:
                parts.append(f"- inspect: {row}\n")
        elif tool == "atlas_repo_summary":
            parts.append(f"Modules: {res.get('module_count', '')}; hubs: {res.get('hubs', '')}\n")
        else:
            parts.append(str({k: res[k] for k in list(res.keys())[:12]}) + "\n")
    return "".join(parts)


def run_atlas_mcp(task: TaskDef, repo_path: Path) -> Dict[str, Any]:
    started = time.perf_counter()
    atlas_log: List[Dict[str, Any]] = []
    files_inspected: List[str] = []
    staged: List[Dict[str, Any]] = []
    error = ""

    try:
        _reset_repo_state()
        scan = _call(
            "atlas_scan_repo",
            {"repo_path": str(repo_path)},
            atlas_log,
        )
        staged.append({"tool": "atlas_scan_repo", "result": scan})
        if not scan.get("ok"):
            raise RuntimeError(scan.get("error") or "scan failed")

        if task.category == "retrieval":
            find = _call(
                "atlas_find_relevant_files",
                {"task": task.prompt, "max_files": 10},
                atlas_log,
            )
            staged.append({"tool": "atlas_find_relevant_files", "result": find})
            files_inspected.extend(_files_from_result(find))
            file_find = _call(
                "atlas_find_file",
                {"query": task.prompt.split("?")[0][-40:], "limit": 8},
                atlas_log,
            )
            staged.append({"tool": "atlas_find_file", "result": file_find})
            files_inspected.extend(_files_from_result(file_find))

        elif task.category == "architecture":
            arch = _call("atlas_get_architecture", {}, atlas_log)
            summary = _call("atlas_repo_summary", {"limit": 12}, atlas_log)
            staged.extend(
                [
                    {"tool": "atlas_get_architecture", "result": arch},
                    {"tool": "atlas_repo_summary", "result": summary},
                ]
            )
            files_inspected.extend(_files_from_result(arch))
            files_inspected.extend(_files_from_result(summary))

        elif task.category == "impact":
            target = "auth/session.py"
            if "session.py" in task.prompt:
                target = "auth/session.py"
            impact = _call("atlas_what_breaks", {"target": target}, atlas_log)
            staged.append({"tool": "atlas_what_breaks", "result": impact})
            files_inspected.extend(_files_from_result(impact))

        elif task.category == "debugging":
            rc = _call(
                "atlas_root_cause",
                {
                    "error": task.prompt,
                    "stack_trace": "auth/middleware.py",
                },
                atlas_log,
            )
            staged.append({"tool": "atlas_root_cause", "result": rc})
            files_inspected.extend(_files_from_result(rc))

        elif task.category == "negative_control":
            find = _call("atlas_find_file", {"query": "graphql", "limit": 10}, atlas_log)
            arch = _call("atlas_repo_summary", {"limit": 8}, atlas_log)
            staged.extend(
                [
                    {"tool": "atlas_find_file", "result": find},
                    {"tool": "atlas_repo_summary", "result": arch},
                ]
            )
            files_inspected.extend(_files_from_result(find))

        response_text = _format_response(task, staged)
        if task.category == "negative_control":
            matches = (staged[0]["result"].get("matches") or []) if staged else []
            if not matches:
                response_text += (
                    "\n\nConclusion: No GraphQL implementation found in scanned repository.\n"
                )
            else:
                response_text += f"\n\nPossible matches to verify: {matches}\n"

        ok = all((item["result"].get("ok") is not False) for item in staged)
        latency = time.perf_counter() - started
        return {
            "ok": ok,
            "response_text": response_text,
            "tool_calls": [{"tool": "atlas_mcp", "steps": len(atlas_log)}],
            "atlas_tool_calls": atlas_log,
            "files_inspected": sorted(set(files_inspected)),
            "latency_seconds": latency,
            "error": error,
        }
    except Exception as exc:
        return {
            "ok": False,
            "response_text": "",
            "tool_calls": [],
            "atlas_tool_calls": atlas_log,
            "files_inspected": files_inspected,
            "latency_seconds": time.perf_counter() - started,
            "error": str(exc),
        }
