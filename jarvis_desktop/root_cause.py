"""#10 Root Cause Mode — Atlas as a senior engineer triaging a failure.

Given an exception / stack trace / error log / failing-test output, identify the
probable root-cause symbols (with confidence + evidence), the supporting files,
and a suggested investigation order. Read-only: no source bodies leave by default.

It reuses the context engine: stack frames give the precise locus; the error text
is run through the task-typed retrieval (which classifies as bug_fix and favors
the call graph + tests, see context_pack #6) to find supporting files; and symbol
slicing (#2) pins each suspect to exact line ranges.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from . import context_pack as cp

# Python:  File ".../adapters.py", line 487, in send
_PY_FRAME = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>[^\s]+)')
# JS/TS:   at send (src/adapters.js:487:12)   |   at src/adapters.js:487:12
_JS_FRAME = re.compile(r'at (?:(?P<func>[\w.$<>]+) \()?(?P<file>[\w./\\-]+\.[a-zA-Z]+):(?P<line>\d+)')
# Java:    at com.x.Foo.bar(Foo.java:42)
_JAVA_FRAME = re.compile(r'at (?P<func>[\w.$]+)\((?P<file>[\w.]+\.java):(?P<line>\d+)\)')
# pytest:  path/to/test_x.py:42: in test_x   |   E   AssertionError: ...
_PYTEST_FRAME = re.compile(r'(?P<file>[\w./\\-]+\.py):(?P<line>\d+): in (?P<func>[\w.<>]+)')
# Exception/last line: "module.ExcType: message"  or  "E   ExcType: message"
_EXC_LINE = re.compile(r'^(?:E\s+)?(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Failure))\b[:\s]?(?P<msg>.*)$')


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").strip()


def parse_error(text: str) -> Dict[str, Any]:
    """Extract ordered stack frames (shallow->deep) + exception type/message."""
    frames: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for rx in (_PY_FRAME, _PYTEST_FRAME, _JS_FRAME, _JAVA_FRAME):
        for m in rx.finditer(text or ""):
            f = _norm(m.group("file"))
            line = int(m.group("line"))
            func = (m.groupdict().get("func") or "").strip()
            key = (f, str(line), func)
            if key in seen:
                continue
            seen.add(key)
            frames.append({"file": f, "line": line, "func": func})

    exc_type, exc_msg = "", ""
    for raw in reversed([ln for ln in (text or "").splitlines() if ln.strip()]):
        m = _EXC_LINE.match(raw.strip())
        if m:
            exc_type = m.group("type")
            exc_msg = (m.group("msg") or "").strip()
            break
    return {"frames": frames, "exception_type": exc_type, "exception_message": exc_msg}


def _match_repo_file(frame_file: str, all_paths: List[str]) -> str:
    """Map an absolute/foreign stack-trace path to a repo-relative path by the
    longest path-suffix match, falling back to a unique basename match."""
    ff = _norm(frame_file)
    if ff in all_paths:
        return ff
    # Longest suffix of the frame path that uniquely matches a repo file.
    parts = ff.split("/")
    for start in range(len(parts)):
        suffix = "/".join(parts[start:])
        if not suffix:
            continue
        hits = [p for p in all_paths if p == suffix or p.endswith("/" + suffix)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1 and start >= len(parts) - 2:
            return sorted(hits, key=len)[0]
    base = os.path.basename(ff)
    bn = [p for p in all_paths if os.path.basename(p) == base]
    return bn[0] if len(bn) == 1 else ""


def _symbol_span_for_func(repo_path: str, rel: str, func: str) -> Optional[Tuple[int, int, str]]:
    """Resolve a frame's function name to a (start,end,kind) span via the AST."""
    if not rel.lower().endswith(".py"):
        return None
    spans = cp._python_symbol_spans(cp._read_small_file(repo_path, rel, max_chars=200_000))
    leaf = (func or "").split(".")[-1]
    for key in (func, leaf):
        if key and key in spans:
            return spans[key]
    return None


def analyze_root_cause(
    repo_path: str,
    error_text: str,
    state: Dict[str, Any],
    *,
    memory: Optional[Dict[str, Any]] = None,
    max_supporting: int = 6,
) -> Dict[str, Any]:
    repo_path = os.path.abspath(repo_path)
    parsed = parse_error(error_text)
    frames = parsed["frames"]
    exc_type = parsed["exception_type"]
    exc_msg = parsed["exception_message"]

    index = state.get("index") or {}
    all_paths = [cp._norm_path(f.get("path", "")) for f in index.get("files") or [] if f.get("path")]
    all_set = set(all_paths)

    # Resolve frames to repo files (shallow->deep as written; deepest = raise site).
    resolved: List[Dict[str, Any]] = []
    for fr in frames:
        rel = _match_repo_file(fr["file"], all_paths)
        in_repo = bool(rel) and rel in all_set
        resolved.append({**fr, "repo_file": rel, "in_repo": in_repo})
    in_repo_frames = [f for f in resolved if f["in_repo"]]

    # Root-cause symbols: deepest in-repo frame is the prime suspect, then callers.
    root_symbols: List[Dict[str, Any]] = []
    for rank, fr in enumerate(reversed(in_repo_frames)):  # deepest first
        span = _symbol_span_for_func(repo_path, fr["repo_file"], fr["func"])
        role = "raise_site" if rank == 0 else "caller_in_path"
        entry: Dict[str, Any] = {
            "file": fr["repo_file"],
            "symbol": fr["func"] or "<module>",
            "frame_line": fr["line"],
            "role": role,
        }
        if span:
            s, e, kind = span
            body = cp._read_small_file(repo_path, fr["repo_file"], max_chars=200_000).splitlines()[s - 1:e]
            entry.update({
                "kind": kind,
                "start_line": s,
                "end_line": e,
                "token_estimate": cp.estimate_tokens("\n".join(body)),
            })
        root_symbols.append(entry)

    # Supporting files via task-typed retrieval seeded with the error text.
    seed_task = " ".join(filter(None, [
        "fix", exc_type, exc_msg[:160],
        " ".join(os.path.basename(f["repo_file"]) for f in in_repo_frames[:4]),
    ])).strip() or (exc_type or "error")
    frame_files = {f["repo_file"] for f in in_repo_frames}
    supporting: List[Dict[str, Any]] = []
    task_type = ""
    try:
        pack = cp.build_context_pack_from_state(repo_path, seed_task, state, memory=memory, max_files=max_supporting + len(frame_files) + 4)
        task_type = (pack.get("task_signals") or {}).get("task_type", "")
        for it in pack.get("recommended_files") or []:
            if it["path"] in frame_files:
                continue
            supporting.append({
                "path": it["path"],
                "reason": it.get("selection_reason") or "related by retrieval",
                "impact": it.get("impact_reason"),
                "score": it.get("relevance_score", it.get("score")),
            })
            if len(supporting) >= max_supporting:
                break
    except Exception:
        supporting = []

    # Confidence.
    score = 0
    score += min(50, 25 * len(in_repo_frames))
    if any("start_line" in s for s in root_symbols):
        score += 25
    if exc_type:
        score += 15
    if supporting:
        score += 10
    score = max(0, min(100, score))
    confidence = "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW"

    # Evidence.
    evidence: List[str] = []
    if exc_type:
        evidence.append(f"Exception: {exc_type}" + (f" - {exc_msg[:120]}" if exc_msg else ""))
    if in_repo_frames:
        deepest = in_repo_frames[-1]
        evidence.append(f"Raise site: `{deepest['repo_file']}` in `{deepest['func']}` (line {deepest['line']})")
        evidence.append(f"{len(in_repo_frames)} of {len(frames)} stack frame(s) resolved to repository files")
    else:
        evidence.append("No stack frame resolved to a repository file — using error-keyword retrieval only")

    # Investigation order.
    order: List[str] = []
    for i, s in enumerate(root_symbols[:4], 1):
        loc = f" (L{s['start_line']}-{s['end_line']})" if s.get("start_line") else f" (frame line {s['frame_line']})"
        order.append(f"{i}. {s['role']}: `{s['file']}` -> `{s['symbol']}`{loc}")
    n = len(order)
    for j, sup in enumerate(supporting[:3], 1):
        order.append(f"{n + j}. supporting: `{sup['path']}` - {sup['reason']}")
    if not order:
        order.append("1. No precise locus; start from the top supporting file and the exception message keywords.")

    return {
        "ok": True,
        "repo_path": repo_path,
        "exception": {"type": exc_type, "message": exc_msg},
        "task_type": task_type or "bug_fix",
        "confidence": confidence,
        "confidence_score": score,
        "root_cause_symbols": root_symbols[:8],
        "supporting_files": supporting,
        "evidence": evidence,
        "stack_frames": resolved[:20],
        "investigation_order": order,
    }
