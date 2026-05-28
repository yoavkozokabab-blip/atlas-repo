"""Investigation graph for causal learning (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.investigation_graph")

GRAPH_PATH = DATA_DIR / "investigation_graph.json"
GRAPH_REPORT_DIR = PROJECT_ROOT / "reports" / "causal_analysis"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"nodes": [], "edges": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(GRAPH_PATH, default=_default_state(), validator=_validate)
    state.setdefault("nodes", [])
    state.setdefault("edges", [])
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(GRAPH_PATH, state)
    try:
        GRAPH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = GRAPH_REPORT_DIR / f"{ts}_graph.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Investigation graph report skipped: %s", exc)


def rebuild_investigation_graph() -> dict[str, Any]:
    from assistant.contradiction_engine import detect_contradictions
    from assistant.hypothesis_engine import refresh_hypotheses
    from assistant.root_cause_engine import sync_root_causes

    sync_root_causes()
    hypotheses = refresh_hypotheses()
    contradictions = detect_contradictions()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for hyp in hypotheses:
        hid = str(hyp.get("id", ""))
        nodes.append({"id": hid, "type": "hypothesis", "label": hyp.get("title", hid)})
        for evidence in hyp.get("evidence") or []:
            eid = f"evidence:{hid}:{hash(str(evidence)) % 100000}"
            nodes.append({"id": eid, "type": "evidence", "label": str(evidence)[:80]})
            edges.append({"from": eid, "to": hid, "type": "supports"})

    try:
        from investigation.blocker_trends import _load as load_trends

        snapshots = load_trends().get("snapshots") or []
        if snapshots:
            latest = snapshots[-1]
            for blocker, count in (latest.get("counts") or {}).items():
                bid = f"blocker:{blocker}"
                nodes.append({"id": bid, "type": "blocker", "label": f"{blocker} ({count})"})
                if hypotheses:
                    edges.append({"from": bid, "to": hypotheses[0].get("id", ""), "type": "correlates"})
    except Exception:
        pass

    for contradiction in contradictions:
        cid = str(contradiction.get("id", ""))
        nodes.append({"id": cid, "type": "contradiction", "label": contradiction.get("message", cid)[:80]})
        edges.append(
            {
                "from": cid,
                "to": contradiction.get("hypothesis_id", ""),
                "type": "contradicts",
            }
        )

    try:
        from assistant.experiment_engine import SAFE_EXPERIMENTS

        for exp in SAFE_EXPERIMENTS[:3]:
            eid = f"experiment:{exp.get('id')}"
            nodes.append({"id": eid, "type": "experiment", "label": exp.get("title", eid)})
            if hypotheses:
                edges.append({"from": eid, "to": hypotheses[0].get("id", ""), "type": "tests"})
    except Exception:
        pass

    state = {"nodes": nodes, "edges": edges, "updated_at": _now()}
    _save(state)
    return state


def show_investigation_graph() -> str:
    graph = rebuild_investigation_graph()
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    lines = [
        f"Investigation graph: {len(nodes)} nodes, {len(edges)} edges",
    ]
    by_type: dict[str, int] = {}
    for node in nodes:
        by_type[node.get("type", "unknown")] = by_type.get(node.get("type", "unknown"), 0) + 1
    for kind, count in sorted(by_type.items()):
        lines.append(f"  {kind}: {count}")
    for node in nodes[:8]:
        lines.append(f"  - [{node.get('type')}] {node.get('label', node.get('id'))[:70]}")
    return "\n".join(lines)


def explain_investigation_graph() -> str:
    graph = rebuild_investigation_graph()
    edges = graph.get("edges") or []
    lines = [
        "Investigation graph structure:",
        "  nodes: blockers, hypotheses, evidence, contradictions, experiments",
        "  edges: supports | correlates | contradicts | tests",
        f"  current edges: {len(edges)}",
    ]
    for edge in edges[:6]:
        lines.append(f"  - {edge.get('from')} --{edge.get('type')}--> {edge.get('to')}")
    return "\n".join(lines)


def trace_causal_chain(root_cause_id: str = "") -> str:
    graph = _load()
    if not graph.get("nodes"):
        graph = rebuild_investigation_graph()
    nodes = {n.get("id"): n for n in graph.get("nodes") or []}
    edges = graph.get("edges") or []
    start = root_cause_id
    if not start:
        for node in graph.get("nodes") or []:
            if node.get("type") == "hypothesis":
                start = node.get("id")
                break
    if not start:
        return "No causal chain available."
    lines = [f"Causal chain for {start}:"]
    lines.append(f"  root: {nodes.get(start, {}).get('label', start)}")
    for edge in edges:
        if edge.get("to") == start:
            src = nodes.get(edge.get("from"), {})
            lines.append(f"  <- [{edge.get('type')}] {src.get('label', edge.get('from'))[:70]}")
        if edge.get("from") == start:
            dst = nodes.get(edge.get("to"), {})
            lines.append(f"  -> [{edge.get('type')}] {dst.get('label', edge.get('to'))[:70]}")
    return "\n".join(lines)
