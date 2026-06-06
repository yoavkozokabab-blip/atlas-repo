"""Phase 172 — Repository Memory Engine.

Persists per-repository scan fingerprints across sessions, enabling:
  - ATLAS_REPOSITORY_MEMORY v1 packet (sent once per session; replaces ATLAS_SESSION v1)
  - ATLAS_DELTA v1 per-question exports (compact; refs memory instead of repeating context)
  - Cross-session delta (what changed since the last time this repo was scanned)

On-disk layout:
  {data_dir}/memory/{repo_id}.json   (one file per distinct repo path)

Where repo_id = sha256(abspath(repo_path))[:16]

Phase 171B projected economics:
  - Memory object: ~120 tokens (once per session)
  - Delta per question: ~100 tokens (down from 364 minimal today)
  - 20Q session reduction: 55–73% across FastAPI / Django / VS Code / Home Assistant

Backward compatible:
  - session_export_packet() continues to work; returns MEMORY packet if available
  - All existing export fields (export, export_full, export_minimal) are unchanged
  - MEMORY_EXPORT is an additive fourth mode in export_metrics()
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

MEMORY_VERSION = "ATLAS_REPOSITORY_MEMORY v1"
DELTA_VERSION = "ATLAS_DELTA v1"
_CHARS_PER_TOKEN = 4.0

# Fields hashed for tamper detection (exclude volatile delta/session_count/memory_hash).
_MEMORY_HASH_KEYS = (
    "version",
    "repo_path",
    "repo_name",
    "repo_id",
    "scan_id",
    "scanned_at",
    "modules",
    "edges",
    "files",
    "graph_health",
    "top_hubs",
    "top_risks",
    "top_subsystems",
    "hub_fingerprint",
    "scan_signature",
    "generated_by_version",
)


def _estimate_tokens(text: str) -> int:
    return max(0, round(len(text or "") / _CHARS_PER_TOKEN))


# --------------------------------------------------------------------------
# Repo identity helpers
# --------------------------------------------------------------------------

def repo_id(repo_path: str) -> str:
    """Stable 16-char identifier for a canonical repo path."""
    norm = os.path.abspath(repo_path or "").replace("\\", "/").lower()
    return hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _scan_id_from_state(state: Dict[str, Any]) -> str:
    scan = state.get("scan") or {}
    repo_path = str(state.get("path") or scan.get("repo_path") or "")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw = (repo_path + ts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:8]


def _hub_fingerprint(top_hubs: List[Dict[str, Any]]) -> str:
    key = json.dumps(
        sorted([(h.get("module", ""), int(h.get("fan_in", 0))) for h in top_hubs]),
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()[:8]


# --------------------------------------------------------------------------
# Memory directory helpers
# --------------------------------------------------------------------------

def _memory_dir(data_dir: str) -> str:
    path = os.path.join(data_dir, "memory")
    os.makedirs(path, exist_ok=True)
    return path


def _memory_path(repo_path: str, data_dir: str) -> str:
    rid = repo_id(repo_path)
    return os.path.join(_memory_dir(data_dir), f"{rid}.json")


# --------------------------------------------------------------------------
# Memory object construction
# --------------------------------------------------------------------------

def compute_memory_hash(memory: Dict[str, Any]) -> str:
    """Stable hash over persisted memory fields (Phase 174B tamper detection)."""
    core = {k: memory.get(k) for k in _MEMORY_HASH_KEYS if k in memory}
    blob = json.dumps(core, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    return hashlib.sha256(blob).hexdigest()


def verify_memory_record(memory: Dict[str, Any], repo_path: str) -> bool:
    """Reject poisoned or tampered on-disk / in-memory records."""
    if not memory or memory.get("version") != MEMORY_VERSION:
        return False
    if repo_id(repo_path) != memory.get("repo_id"):
        return False
    if os.path.abspath(repo_path or "") != os.path.abspath(str(memory.get("repo_path") or "")):
        return False
    declared = memory.get("memory_hash")
    if not declared or declared != compute_memory_hash(memory):
        return False
    return True


def build_memory(state: Dict[str, Any], *, generated_by_version: str = "") -> Dict[str, Any]:
    """Build an ATLAS_REPOSITORY_MEMORY v1 object from current product state.

    Safe with partial state — missing fields get safe defaults.
    Does not write to disk; call persist() for that.
    """
    scan = state.get("scan") or {}
    index = state.get("index") or {}

    repo_path = str(state.get("path") or scan.get("repo_path") or "")
    repo_name = (
        scan.get("repo_name")
        or os.path.basename(repo_path.rstrip("/\\"))
        or "repository"
    )

    # Graph health
    gh = scan.get("graph_health") or {}
    if isinstance(gh, dict):
        gh_label = gh.get("label") or "unknown"
    elif gh:
        gh_label = str(gh)
    else:
        gh_label = "unknown"

    # Top hubs (top 5, sorted by fan_in desc)
    raw_hubs = scan.get("top_hubs") or []
    top_hubs = [
        {"module": h.get("module", ""), "fan_in": int(h.get("fan_in", 0))}
        for h in raw_hubs[:5]
        if h.get("module")
    ]

    # Top risks (top 5) — entries may be dicts {module: ...} or bare strings
    top_risks = []
    for r in (scan.get("top_risks") or [])[:5]:
        if isinstance(r, dict):
            val = str(r.get("module") or r.get("path") or "")
        else:
            val = str(r or "")
        if val:
            top_risks.append(val)

    # Subsystems (top 5 production code subsystems by file count)
    subs = sorted(
        (s for s in index.get("subsystems", [])
         if s.get("role_counts", {}).get("production_code", 0) > 0),
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    top_subsystems = [s.get("name", "") for s in subs[:5] if s.get("name")]

    scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sid = hashlib.sha256(
        (repo_path + scanned_at).encode("utf-8", errors="ignore")
    ).hexdigest()[:8]

    sig_v2 = scan.get("signature_v2") or {}
    scan_signature = sig_v2.get("signature") or (scan.get("cache") or {}).get("signature") or ""

    memory = {
        "version": MEMORY_VERSION,
        "repo_path": repo_path,
        "repo_name": repo_name,
        "repo_id": repo_id(repo_path),
        "scan_id": sid,
        "scanned_at": scanned_at,
        "modules": int(scan.get("module_count", 0)),
        "edges": int(scan.get("dependency_edges", 0)),
        "files": int(scan.get("file_count", 0)),
        "graph_health": gh_label,
        "top_hubs": top_hubs,
        "top_risks": top_risks,
        "top_subsystems": top_subsystems,
        "hub_fingerprint": _hub_fingerprint(top_hubs),
        "scan_signature": scan_signature,
        "generated_by_version": generated_by_version or "unknown",
        "session_count": 1,  # overwritten by merge_with_delta()
        "delta": None,       # overwritten by merge_with_delta()
    }
    memory["memory_hash"] = compute_memory_hash(memory)
    return memory


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def persist(memory: Dict[str, Any], data_dir: str) -> Tuple[str, bool, str]:
    """Write memory to disk atomically. Returns (path, ok, error_message)."""
    repo_path = memory.get("repo_path", "")
    if not repo_path:
        return "", False, "missing repo_path"
    path = _memory_path(repo_path, data_dir)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return "", False, f"{type(exc).__name__}: {exc}"
    return path, True, ""


def load(repo_path: str, data_dir: str) -> Optional[Dict[str, Any]]:
    """Load persisted memory for this repo. Returns None if not found or corrupt."""
    if not repo_path:
        return None
    path = _memory_path(repo_path, data_dir)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not verify_memory_record(data, repo_path):
            return None
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Delta computation
# --------------------------------------------------------------------------

def compute_delta(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Diff current memory against previous scan memory."""
    if not previous:
        return {
            "has_delta": False,
            "first_scan": True,
            "session_count": 1,
            "modules_delta": 0,
            "edges_delta": 0,
            "new_hubs": [],
            "removed_hubs": [],
            "new_risks": [],
            "removed_risks": [],
            "hub_topology_changed": False,
            "previous_scan_at": None,
        }

    mod_d = current.get("modules", 0) - previous.get("modules", 0)
    edge_d = current.get("edges", 0) - previous.get("edges", 0)

    cur_hubs = {h["module"] for h in current.get("top_hubs", []) if h.get("module")}
    prev_hubs = {h["module"] for h in previous.get("top_hubs", []) if h.get("module")}
    new_hubs = sorted(cur_hubs - prev_hubs)
    removed_hubs = sorted(prev_hubs - cur_hubs)

    cur_risks = set(current.get("top_risks", []))
    prev_risks = set(previous.get("top_risks", []))

    hub_changed = bool(
        new_hubs or removed_hubs
        or current.get("hub_fingerprint") != previous.get("hub_fingerprint")
    )

    session_count = int(previous.get("session_count", 1)) + 1
    has_delta = bool(mod_d or edge_d or hub_changed
                     or (cur_risks - prev_risks) or (prev_risks - cur_risks))

    return {
        "has_delta": has_delta,
        "first_scan": False,
        "session_count": session_count,
        "modules_delta": mod_d,
        "edges_delta": edge_d,
        "new_hubs": new_hubs,
        "removed_hubs": removed_hubs,
        "new_risks": sorted(cur_risks - prev_risks),
        "removed_risks": sorted(prev_risks - cur_risks),
        "hub_topology_changed": hub_changed,
        "previous_scan_at": previous.get("scanned_at"),
    }


def merge_with_delta(
    memory: Dict[str, Any],
    delta: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a new memory dict with session_count and delta embedded."""
    out = dict(memory)
    out["session_count"] = delta.get("session_count", 1)
    out["delta"] = delta
    return out


# --------------------------------------------------------------------------
# ATLAS_REPOSITORY_MEMORY v1 text
# --------------------------------------------------------------------------

def memory_text(memory: Dict[str, Any]) -> str:
    """Render ATLAS_REPOSITORY_MEMORY v1 text (~80–130 tokens).

    Sent once per session. Contains stable architectural facts that do not
    need to be repeated in each per-question delta.
    """
    delta = memory.get("delta") or {}
    session_n = int(memory.get("session_count", 1))
    first = delta.get("first_scan", True)

    mod = memory.get("modules", 0)
    edges = memory.get("edges", 0)
    gh = memory.get("graph_health", "unknown")
    mod_d = delta.get("modules_delta", 0)
    edge_d = delta.get("edges_delta", 0)

    lines = [
        MEMORY_VERSION,
        f"repo: {memory.get('repo_name', 'repository')}  "
        f"session: {session_n}  scan_id: {memory.get('scan_id', '')}",
    ]

    # Modules / edges line
    if first or not delta.get("has_delta"):
        lines.append(
            f"modules: {mod}  edges: {edges}  "
            f"files: {memory.get('files', 0)}  graph_health: {gh}"
        )
    else:
        mod_s = (f"{mod}({'+' if mod_d >= 0 else ''}{mod_d})" if mod_d else str(mod))
        edge_s = (f"{edges}({'+' if edge_d >= 0 else ''}{edge_d})" if edge_d else str(edges))
        lines.append(
            f"modules: {mod_s}  edges: {edge_s}  "
            f"files: {memory.get('files', 0)}  graph_health: {gh}"
        )

    # Hubs
    hubs = memory.get("top_hubs") or []
    if hubs:
        hub_parts = [
            f"{h['module']} ({h['fan_in']})"
            for h in hubs[:3]
            if h.get("module")
        ]
        lines.append(f"hubs: {', '.join(hub_parts)}")

    # Risks
    risks = memory.get("top_risks") or []
    if risks:
        lines.append(f"risks: {', '.join(risks[:3])}")

    # Subsystems
    subs = memory.get("top_subsystems") or []
    if subs:
        lines.append(f"subsystems: {', '.join(subs[:5])}")

    # Delta summary
    if first:
        lines.append("delta: none  [first scan]")
    elif not delta.get("has_delta"):
        prev = delta.get("previous_scan_at") or ""
        lines.append(f"delta: none  [topology unchanged since {prev}]")
    else:
        prev = delta.get("previous_scan_at") or ""
        parts: List[str] = []
        if mod_d:
            parts.append(f"{'+' if mod_d >= 0 else ''}{mod_d} modules")
        if edge_d:
            parts.append(f"{'+' if edge_d >= 0 else ''}{edge_d} edges")
        for h in delta.get("new_hubs", [])[:1]:
            parts.append(f"new_hub: {h}")
        for h in delta.get("removed_hubs", [])[:1]:
            parts.append(f"removed_hub: {h}")
        for r in delta.get("new_risks", [])[:1]:
            parts.append(f"new_risk: {r}")
        lines.append(
            f"delta: {', '.join(parts) or 'minor changes'}  since {prev}"
        )

    return "\n".join(lines)


def memory_packet(memory: Dict[str, Any]) -> Dict[str, Any]:
    """Build the MEMORY-mode packet (analogous to atlas_export.session_context())."""
    text = memory_text(memory)
    return {
        "text": text,
        "mode": "MEMORY",
        "tokens": _estimate_tokens(text),
        "version": MEMORY_VERSION,
        "session_count": int(memory.get("session_count", 1)),
        "repo_id": memory.get("repo_id", ""),
        "scan_id": memory.get("scan_id", ""),
        "has_delta": bool((memory.get("delta") or {}).get("has_delta")),
    }


# --------------------------------------------------------------------------
# ATLAS_DELTA v1 per-question text
# --------------------------------------------------------------------------

def _delta_bullets(items: List[str], sep: str = ", ") -> str:
    return sep.join(str(x) for x in items if x)


def _trunc(s: str, n: int) -> str:
    """Truncate string to n chars with ellipsis."""
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def _delta_lines_build(plan: Dict[str, Any], *, goal: str = "") -> List[str]:
    """Compact ATLAS_DELTA v1 for build workflow.

    Target: ≤ 120 tokens. Strips markdown scaffolding, cuts lists aggressively.
    Stable context (hubs/risks/subsystems) is already in ATLAS_REPOSITORY_MEMORY v1.
    """
    from jarvis_desktop.atlas_export import _dedupe_paths, _concept_label, _evidence_lines

    # Files: top 4 (not 5) — impl_order is often the same first 2-3 files
    files = _dedupe_paths(
        list(plan.get("files_to_inspect_first") or [])
        + list(plan.get("likely_affected_modules") or []),
        4,
    )
    # Breaks: top 3 only
    may_break = _dedupe_paths(
        list(plan.get("what_may_break") or plan.get("files_likely_to_break") or []), 3
    )
    # Order: only emit if different from first 2 files; max 2
    impl_raw = _dedupe_paths(list(plan.get("implementation_order") or []), 2)
    impl = impl_raw if impl_raw and impl_raw[:2] != files[:2] else []
    # Concept: label only (no quality annotation)
    concept = _concept_label(plan).split("(")[0].strip()
    # Evidence: 1 item, truncated
    evidence = _evidence_lines(plan, 1)
    conf = plan.get("confidence", "low")
    risk = plan.get("risk_level", "unknown")

    lines = [
        f"goal: {_trunc(goal or plan.get('goal') or plan.get('intent') or '', 80)}  "
        f"conf: {conf}  risk: {risk}",
    ]
    if concept:
        lines.append(f"concept: {concept}")
    if files:
        lines.append(f"files: {_delta_bullets(files)}")
    if impl:
        lines.append(f"order: {_delta_bullets(impl)}")
    if may_break:
        lines.append(f"breaks: {_delta_bullets(may_break)}")
    if evidence:
        lines.append(f"evidence: {_trunc(_delta_bullets(evidence, '; '), 90)}")
    # No caveat in delta — user knows static analysis has limits
    return lines


def _delta_lines_investigate(plan: Dict[str, Any], *, goal: str = "") -> List[str]:
    """Compact ATLAS_DELTA v1 for investigate workflow.

    Target: ≤ 130 tokens. Uses original short symptom (passed as goal) not
    the verbose plan.symptom_summary expansion.
    """
    from jarvis_desktop.atlas_export import _dedupe_paths, _evidence_lines

    # Use original short symptom when available
    symptom = _trunc(goal or plan.get("symptom_summary") or plan.get("symptom") or "", 80)
    root = _trunc(
        plan.get("most_likely_root_cause") or plan.get("most_likely_source") or "", 80
    )
    hyps = plan.get("hypotheses") or []
    h1 = hyps[0] if hyps else {}
    # Top 3 files only
    h1_files = _dedupe_paths(
        list(h1.get("files_involved") or plan.get("likely_modules") or []), 3
    )
    # 1 verify + 1 fix, truncated
    verify = list(plan.get("verification_checklist") or plan.get("verification_steps") or [])[:1]
    fix = list(plan.get("minimal_fix_strategy") or [])[:1]
    conf = plan.get("confidence", "low")

    lines = [f"symptom: {symptom}  conf: {conf}"]
    if root:
        lines.append(f"root_cause: {root}")
    if h1:
        h1_title = _trunc(h1.get("title", ""), 60)
        lines.append(f"hypothesis: {h1_title}")
    if h1_files:
        lines.append(f"files: {_delta_bullets(h1_files)}")
    if verify:
        lines.append(f"verify: {_trunc(str(verify[0]), 80)}")
    if fix:
        lines.append(f"fix: {_trunc(str(fix[0]), 80)}")
    return lines


def _delta_lines_impact(result: Dict[str, Any]) -> List[str]:
    """Compact ATLAS_DELTA v1 for impact workflow.

    Target: ≤ 100 tokens.
    """
    from jarvis_desktop.atlas_export import _dedupe_paths, _evidence_lines

    target = result.get("target") or ""
    # Direct: top 5; indirect: top 3
    direct = _dedupe_paths(list(result.get("direct_impact") or []), 5)
    indirect = _dedupe_paths(list(result.get("indirect_impact") or []), 3)
    sem = _trunc(result.get("semantic_label") or "", 50)
    conf = result.get("confidence", "low")
    risk = result.get("risk_level", "unknown")

    lines = [f"target: {target}  conf: {conf}  risk: {risk}"]
    if sem:
        lines.append(f"semantic: {sem}")
    if direct:
        lines.append(f"direct: {_delta_bullets(direct)}")
    if indirect:
        lines.append(f"indirect: {_delta_bullets(indirect)}")
    return lines


def delta_text(
    workflow: str,
    *,
    plan_or_result: Dict[str, Any],
    memory_ref: str = "",
    goal: str = "",
) -> str:
    """Render ATLAS_DELTA v1 text (~80–110 tokens).

    Does NOT repeat stable session facts (those are in ATLAS_REPOSITORY_MEMORY v1).
    """
    plan = plan_or_result.get("plan") or plan_or_result

    header_parts = [DELTA_VERSION]
    if memory_ref:
        header_parts.append(f"ref: {memory_ref}")

    if workflow == "build":
        content_lines = _delta_lines_build(plan, goal=goal)
    elif workflow == "investigate":
        content_lines = _delta_lines_investigate(plan, goal=goal)
    elif workflow == "impact":
        content_lines = _delta_lines_impact(plan_or_result)
    else:
        return ""

    return "\n".join(header_parts + content_lines)


# --------------------------------------------------------------------------
# State integration
# --------------------------------------------------------------------------

def update_after_scan(
    state: Dict[str, Any],
    data_dir: str,
    *,
    generated_by_version: str = "",
) -> Dict[str, Any]:
    """Build memory, diff against previous, persist, cache in state.

    Call after every successful scan (cache-hit or cache-miss).
    Returns the memory packet cached in state["repository_memory"].
    """
    if not state.get("scan"):
        return {}

    memory = build_memory(state, generated_by_version=generated_by_version)
    repo_path = memory.get("repo_path", "")

    previous = load(repo_path, data_dir) if repo_path else None
    if previous and previous.get("scan_signature") and memory.get("scan_signature"):
        if previous["scan_signature"] != memory["scan_signature"]:
            previous = None  # stale cross-session memory — start fresh delta

    delta = compute_delta(memory, previous)
    memory = merge_with_delta(memory, delta)
    memory["memory_hash"] = compute_memory_hash(memory)

    persist_ok = True
    persist_err = ""
    if repo_path:
        _path, persist_ok, persist_err = persist(memory, data_dir)
        if not persist_ok:
            # Do not claim durable cross-session memory when disk write failed.
            delta = compute_delta(memory, None)
            memory = merge_with_delta(memory, delta)
            memory["memory_hash"] = compute_memory_hash(memory)

    state["memory_persistence_status"] = "ok" if persist_ok else "failed"
    state["memory_persistence_error"] = persist_err or ""

    packet = memory_packet(memory)
    packet["memory_persistence_status"] = state["memory_persistence_status"]
    if not persist_ok:
        packet["persistent_memory_available"] = False
    state["repository_memory"] = packet
    state["session_export"] = packet
    state["_current_memory"] = memory
    return packet


def clear_for_path_change(state: Dict[str, Any]) -> None:
    """Clear memory/session state when repository path changes (Phase 172 mitigation A1).

    Prevents stale session_export from answering questions about the wrong repo.
    """
    state["session_export"] = None
    state["repository_memory"] = None
    state.pop("_current_memory", None)
    state.pop("memory_persistence_status", None)
    state.pop("memory_persistence_error", None)


def get_memory_ref(state: Dict[str, Any]) -> str:
    """Return the scan_id to use as memory_ref in delta exports."""
    mem = state.get("_current_memory") or {}
    return mem.get("scan_id") or (state.get("repository_memory") or {}).get("scan_id") or ""
