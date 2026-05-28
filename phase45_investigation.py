"""Phase 45 read-only project and trading investigation engine."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT

REPORT_SUFFIXES = {".csv", ".json", ".txt", ".md", ".log"}
CODE_SUFFIXES = {".py", ".ps1", ".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".txt", ".md"}
MAX_FILES_PER_BUCKET = 12
MAX_READ_CHARS = 5000
PHASE46_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations"

TRADING_SCAN_DIRS = (
    "reports/live_paper",
    "reports/live_paper/dual",
    "reports/live_paper/state",
    "reports/live_paper_trials",
    "reports/backtests",
    "backtests",
    "configs",
    "config",
    "universe",
    "universes",
    "state",
)

COMPARE_CHECKS = (
    ("signal mismatch", ("signal", "score", "candidate", "trigger")),
    ("entry mismatch", ("entry", "delayed", "filled", "eligible")),
    ("ranking mismatch", ("rank", "ranking", "sort", "top")),
    ("risk sizing mismatch", ("risk", "size", "position", "exposure")),
    ("stale price issues", ("stale", "price", "quote", "bar")),
    ("universe differences", ("universe", "symbols", "watchlist", "ticker")),
    ("config drift", ("config", "drift", "threshold", "parameter")),
    ("data window differences", ("window", "lookback", "history", "bars")),
    ("execution/slippage assumptions", ("slippage", "spread", "execution", "commission")),
    ("paper/live state problems", ("state", "position", "open_positions", "paper")),
)

BEHAVIOR_FILES = (
    "algo_scanner/backtest/fib_quality.py",
    "algo_scanner/strategy/real_algo.py",
    "services/live_paper_engine.py",
    "services/live_dual_paper_cycle.py",
    "services/portfolio_manager.py",
    "analytics/portfolio_engine.py",
)

BEHAVIOR_STEPS = (
    ("signal detection", ("signal", "setup", "fib", "quality", "candidate")),
    ("ranking", ("rank", "ranking", "score", "sort")),
    ("entry gate", ("entry", "eligible", "gate", "reject", "confirm")),
    ("delayed entry", ("delayed", "delay", "pending", "next_bar")),
    ("stop loss", ("stop", "stop_loss", "sl")),
    ("target / RR", ("target", "rr", "reward", "take_profit")),
    ("position sizing", ("size", "position_size", "risk_per_trade", "qty")),
    ("portfolio cap", ("max_open", "portfolio", "cap", "exposure")),
    ("paper/live decision", ("paper", "live", "execute", "adapter", "order")),
)

DIFF_CATEGORIES = (
    ("signal rules", ("signal", "fib", "quality", "trigger")),
    ("entry timing", ("entry", "delayed", "next_bar", "last_closed")),
    ("bar selection", ("last_closed", "current_bar", "iloc[-1]", "completed")),
    ("ranking", ("rank", "score", "sort", "top")),
    ("stop handling", ("stop", "stop_loss", "trail")),
    ("exits", ("exit", "target", "take_profit", "close")),
    ("risk sizing", ("risk", "size", "position", "qty")),
    ("portfolio caps", ("max_open", "cap", "portfolio", "exposure")),
    ("universe", ("universe", "symbols", "tickers", "watchlist")),
    ("data source", ("data_source", "provider", "ohlcv", "quote")),
    ("data window", ("lookback", "window", "history", "bars")),
    ("slippage / gap assumptions", ("slippage", "spread", "gap", "commission")),
)

BUG_PATTERNS = (
    ("inconsistent config names", "medium", (r"os\.getenv\(", r"config\.", r"settings\."), "Config naming may drift between live/backtest."),
    ("duplicated logic", "medium", (r"def .*signal", r"def .*rank", r"def .*entry"), "Similar logic may exist in multiple paths."),
    ("stale state", "high", (r"state", r"cache", r"last_"), "State reuse can explain live/backtest divergence."),
    ("off-by-one bar issues", "high", (r"iloc\[-1\]", r"iloc\[-2\]", r"shift\(", r"last_closed"), "Bar indexing differences often cause signal mismatch."),
    ("lookahead bias risk", "high", (r"future", r"lookahead", r"iloc\[-1\]", r"current_bar"), "Backtests can accidentally see unavailable bar data."),
    ("ranking order dependence", "medium", (r"sort_values", r"sorted\(", r"rank"), "Unstable ranking can change selected trades."),
    ("disabled execution path", "high", (r"execution.*disabled", r"n_execution_attempts", r"adapter.*None"), "Live may detect signals but never place paper/live orders."),
    ("stale prices", "high", (r"stale", r"price", r"quote"), "Stale price gates can block entries in live only."),
    ("silent exception handling", "medium", (r"except Exception", r"pass"), "Broad exception handling can hide live-path failures."),
    ("mismatched defaults", "medium", (r"default", r"get\(", r"os\.getenv"), "Defaults may differ between live and backtest paths."),
)


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: str
    path: str
    confidence: float
    evidence: str


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    confidence: float
    evidence: str


@dataclass(frozen=True)
class RankedHypothesis:
    severity: str
    title: str
    evidence: list[Evidence]
    why: str
    verify: str
    files: list[str]
    suggested_test: str
    confidence: float


@dataclass(frozen=True)
class Evidence:
    path: str
    detail: str


def _safe_rel(path: Path, root: Path | None = None) -> str:
    base = root or PROJECT_ROOT
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _iter_files(root: Path, *, suffixes: set[str] | None = None, limit: int = 200) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    out: list[Path] = []
    try:
        for path in root.rglob("*"):
            if len(out) >= limit:
                break
            if not path.is_file():
                continue
            if suffixes and path.suffix.lower() not in suffixes:
                continue
            parts = {p.lower() for p in path.parts}
            if parts & {".git", "__pycache__", ".pytest_cache", "node_modules", "tests_tmp"}:
                continue
            out.append(path)
    except OSError:
        return out
    return sorted(out, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)


def _latest_files(root: Path, *, suffixes: set[str] | None = None, limit: int = MAX_FILES_PER_BUCKET) -> list[Path]:
    return _iter_files(root, suffixes=suffixes, limit=500)[:limit]


def _read_preview(path: Path, *, max_chars: int = MAX_READ_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(unreadable: {exc})"
    if len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated)"
    return text


def _line_hits(path: Path, keywords: Iterable[str], *, max_hits: int = 8) -> list[str]:
    text = _read_preview(path, max_chars=MAX_READ_CHARS)
    hits: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(k.lower() in lower for k in keywords):
            hits.append(line.strip()[:220])
        if len(hits) >= max_hits:
            break
    return hits


def _line_hits_with_numbers(path: Path, keywords: Iterable[str], *, max_hits: int = 6) -> list[str]:
    text = _read_preview(path, max_chars=MAX_READ_CHARS)
    hits: list[str] = []
    for idx, line in enumerate(text.splitlines(), 1):
        lower = line.lower()
        if any(k.lower() in lower for k in keywords):
            hits.append(f"{path}:{idx}: {line.strip()[:220]}")
        if len(hits) >= max_hits:
            break
    return hits


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "  - No evidence found."
    return f"## {title}\n{body}"


def _project_roots() -> list[tuple[str, Path]]:
    roots = [("JARVIS project", PROJECT_ROOT)]
    if TRADING_PROJECT_ROOT != PROJECT_ROOT:
        roots.append(("Trading project", TRADING_PROJECT_ROOT))
    return roots


def inspect_project() -> str:
    lines = ["Phase 45 project inspection (read-only)."]
    for label, root in _project_roots():
        exists = root.exists()
        lines.append(f"- {label}: {root} ({'exists' if exists else 'missing'})")
        if not exists:
            continue
        files = _iter_files(root, suffixes=CODE_SUFFIXES, limit=400)
        lines.append(f"  files sampled: {len(files)}")
        for path in files[:8]:
            lines.append(f"  evidence: {_safe_rel(path, root)}")
    lines.append("Next actions: summarize current project; find failing tests; run safe diagnostics.")
    return "\n".join(lines)


def summarize_current_project() -> str:
    root = PROJECT_ROOT
    files = _iter_files(root, suffixes=CODE_SUFFIXES, limit=500)
    by_suffix: dict[str, int] = {}
    for path in files:
        by_suffix[path.suffix.lower() or "(none)"] = by_suffix.get(path.suffix.lower() or "(none)", 0) + 1
    evidence = [f"- {suffix}: {count}" for suffix, count in sorted(by_suffix.items())[:12]]
    recent = [f"- {_safe_rel(p, root)}" for p in files[:10]]
    return "\n\n".join(
        [
            _section("Project Summary", [f"- Root: {root}", f"- Sampled files: {len(files)}"]),
            _section("File Types", evidence),
            _section("Recent Files", recent),
            _section("Next Actions", ["- inspect project", "- find recent code changes", "- run safe diagnostics"]),
        ]
    )


def find_failing_tests() -> str:
    cache = PROJECT_ROOT / ".pytest_cache" / "v" / "cache" / "lastfailed"
    lines = ["Read-only failing test scan."]
    if cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            lines.append(f"- Evidence: {cache} unreadable ({exc})")
        else:
            failed = sorted(str(k) for k, v in data.items() if v)
            lines.append(f"- Evidence: {cache}")
            lines.append(f"- Failing tests recorded: {len(failed)}")
            lines.extend(f"  - {item}" for item in failed[:20])
            if failed:
                lines.append("Next actions: explain latest error; inspect relevant test file; propose patch only after approval.")
                return "\n".join(lines)
    terminals = Path.home() / ".cursor" / "projects" / "c-J-A-R-V-I-S" / "terminals"
    recent = _latest_files(terminals, suffixes={".txt"}, limit=8)
    error_hits: list[str] = []
    for path in recent:
        error_hits.extend(f"{path.name}: {h}" for h in _line_hits(path, ("FAILED", "ERROR", "AssertionError", "Traceback"), max_hits=4))
    if error_hits:
        lines.append(f"- Evidence: {terminals}")
        lines.extend(f"  - {h}" for h in error_hits[:20])
    else:
        lines.append("- No recorded failing tests found in pytest cache or recent terminal logs.")
    lines.append("Next actions: run a focused test command manually or ask JARVIS to inspect a specific failure.")
    return "\n".join(lines)


def explain_latest_error() -> str:
    candidates: list[Path] = []
    candidates.extend(_latest_files(Path.home() / ".cursor" / "projects" / "c-J-A-R-V-I-S" / "terminals", suffixes={".txt"}, limit=10))
    candidates.extend(_latest_files(PROJECT_ROOT / "reports", suffixes={".log", ".txt"}, limit=10))
    hits: list[str] = []
    for path in candidates:
        path_hits = _line_hits(path, ("traceback", "error", "failed", "exception", "timeout", "killed"), max_hits=6)
        if path_hits:
            hits.append(f"- Evidence: {path}")
            hits.extend(f"  - {h}" for h in path_hits)
            break
    if not hits:
        hits = ["- No recent error evidence found in terminal/report logs."]
    return "\n".join(
        [
            "Latest error explanation (read-only).",
            *hits,
            "Likely next actions:",
            "- Identify the command/test that produced the error.",
            "- Inspect the referenced file and traceback frame.",
            "- Propose a patch only after explicit approval.",
        ]
    )


def _scan_trading_sources() -> list[Path]:
    paths: list[Path] = []
    for rel in TRADING_SCAN_DIRS:
        paths.extend(_latest_files(TRADING_PROJECT_ROOT / rel, suffixes=REPORT_SUFFIXES | CODE_SUFFIXES, limit=MAX_FILES_PER_BUCKET))
    paths.extend(_latest_files(TRADING_PROJECT_ROOT, suffixes={".json", ".yaml", ".yml", ".toml", ".ini"}, limit=20))
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:80]


def _specific_behavior_paths() -> list[Path]:
    return [TRADING_PROJECT_ROOT / rel for rel in BEHAVIOR_FILES]


def _collect_behavior_files() -> list[Path]:
    paths = [p for p in _specific_behavior_paths() if p.is_file()]
    if paths:
        return paths
    fallback: list[Path] = []
    for keyword in ("backtest", "strategy", "live", "portfolio", "risk", "engine"):
        fallback.extend(
            p
            for p in _iter_files(TRADING_PROJECT_ROOT, suffixes={".py"}, limit=250)
            if keyword in str(p).lower()
        )
    return sorted(set(fallback), key=str)[:30]


def _collect_evidence(paths: list[Path], keywords: Iterable[str], *, limit: int = 5) -> list[Evidence]:
    evidence: list[Evidence] = []
    for path in paths:
        hits = _line_hits(path, keywords, max_hits=2)
        if hits:
            evidence.append(Evidence(str(path), " | ".join(hits)[:450]))
        if len(evidence) >= limit:
            break
    return evidence


def _format_evidence(evidence: list[Evidence]) -> list[str]:
    if not evidence:
        return ["  evidence: no local snippet found; treat as hypothesis"]
    return [f"  evidence: {ev.path} :: {ev.detail}" for ev in evidence]


def build_investigation_graph_data() -> tuple[list[GraphNode], list[GraphEdge]]:
    paths = _scan_trading_sources()
    paths.extend(_collect_behavior_files())
    paths.extend(_latest_files(PROJECT_ROOT / ".pytest_cache" / "v" / "cache", suffixes={".json"}, limit=5))
    paths.extend(_latest_files(PROJECT_ROOT, suffixes={".py", ".json", ".yaml", ".yml", ".toml"}, limit=20))
    nodes: list[GraphNode] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        lower = str(path).lower()
        if "config" in lower or path.suffix.lower() in {".yaml", ".yml", ".toml", ".ini", ".env"}:
            kind = "config"
        elif "backtest" in lower:
            kind = "backtest_output" if path.suffix.lower() != ".py" else "backtest_code"
        elif "live_paper" in lower or "report" in lower:
            kind = "live_report"
        elif "state" in lower:
            kind = "state_file"
        elif "universe" in lower or "symbols" in lower:
            kind = "universe_file"
        elif "test" in lower:
            kind = "failing_test"
        elif path.suffix.lower() == ".py":
            kind = "code"
        else:
            kind = "evidence"
        snippet = _read_preview(path, max_chars=500).splitlines()
        evidence = next((s.strip() for s in snippet if s.strip()), "(empty)")
        nodes.append(
            GraphNode(
                node_id=f"n{len(nodes) + 1}",
                kind=kind,
                path=str(path),
                confidence=0.75 if kind == "evidence" else 0.85,
                evidence=evidence[:220],
            )
        )
    edges: list[GraphEdge] = []
    for src in nodes:
        for dst in nodes:
            if src.node_id == dst.node_id:
                continue
            relation = ""
            confidence = 0.0
            if src.kind == "config" and dst.kind in {"code", "backtest_code", "live_report"}:
                relation, confidence = "may_configure", 0.55
            elif src.kind in {"backtest_code", "code"} and dst.kind == "live_report":
                relation, confidence = "may_produce_or_explain", 0.45
            elif src.kind == "state_file" and dst.kind == "live_report":
                relation, confidence = "state_feeds_report", 0.70
            elif src.kind == "universe_file" and dst.kind in {"backtest_output", "live_report"}:
                relation, confidence = "universe_scope", 0.65
            if relation:
                edges.append(
                    GraphEdge(
                        source=src.node_id,
                        target=dst.node_id,
                        relation=relation,
                        confidence=confidence,
                        evidence=f"{src.path} -> {dst.path}",
                    )
                )
            if len(edges) >= 80:
                break
        if len(edges) >= 80:
            break
    return nodes[:80], edges[:80]


def build_investigation_graph() -> str:
    nodes, edges = build_investigation_graph_data()
    lines = [
        "Investigation graph (read-only)",
        f"Nodes: {len(nodes)}",
        f"Edges: {len(edges)}",
        "",
        "Nodes:",
    ]
    for node in nodes[:30]:
        lines.append(
            f"- {node.node_id} [{node.kind}] confidence={node.confidence:.2f} path={node.path}"
        )
        lines.append(f"  evidence: {node.evidence}")
    lines.append("")
    lines.append("Edges:")
    for edge in edges[:30]:
        lines.append(
            f"- {edge.source} -> {edge.target} relation={edge.relation} confidence={edge.confidence:.2f}"
        )
        lines.append(f"  evidence: {edge.evidence}")
    if not nodes:
        lines.append("No graph nodes found. Evidence paths may be missing.")
    return "\n".join(lines)


def show_investigation_graph() -> str:
    return build_investigation_graph()


def search_investigation_graph(query: str) -> str:
    query = (query or "").strip().lower()
    nodes, edges = build_investigation_graph_data()
    if not query:
        return "Search investigation graph: provide a query, e.g. search investigation graph stale price"
    lines = [f"Investigation graph search: {query}"]
    matched = 0
    for node in nodes:
        hay = f"{node.kind} {node.path} {node.evidence}".lower()
        if query in hay:
            matched += 1
            lines.append(f"- node {node.node_id} [{node.kind}] confidence={node.confidence:.2f}")
            lines.append(f"  path: {node.path}")
            lines.append(f"  evidence: {node.evidence}")
    for edge in edges:
        if query in f"{edge.relation} {edge.evidence}".lower():
            matched += 1
            lines.append(f"- edge {edge.source}->{edge.target} {edge.relation} confidence={edge.confidence:.2f}")
            lines.append(f"  evidence: {edge.evidence}")
    if matched == 0:
        lines.append("No matching graph evidence found.")
    return "\n".join(lines)


def inspect_latest_live_report() -> str:
    roots = [TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual", TRADING_PROJECT_ROOT / "reports" / "live_paper"]
    files: list[Path] = []
    for root in roots:
        files.extend(_latest_files(root, suffixes=REPORT_SUFFIXES, limit=10))
    if not files:
        return f"No live report files found.\nEvidence checked: {[str(r) for r in roots]}\nNext action: verify report path or run diagnostics (read-only)."
    latest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    preview = _read_preview(latest, max_chars=3500)
    return f"Latest live report\nEvidence: {latest}\n\n{preview}\n\nNext actions: compare live vs backtest; inspect state files."


def inspect_latest_backtest_report() -> str:
    roots = [TRADING_PROJECT_ROOT / "reports" / "backtests", TRADING_PROJECT_ROOT / "backtests", TRADING_PROJECT_ROOT / "reports"]
    files: list[Path] = []
    for root in roots:
        files.extend([p for p in _latest_files(root, suffixes=REPORT_SUFFIXES, limit=20) if "backtest" in str(p).lower()])
    if not files:
        return f"No backtest report files found.\nEvidence checked: {[str(r) for r in roots]}\nNext action: point JARVIS at a report path or generate a read-only findings report."
    latest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    preview = _read_preview(latest, max_chars=3500)
    return f"Latest backtest report\nEvidence: {latest}\n\n{preview}\n\nNext actions: compare live vs backtest; inspect config drift."


def _comparison_evidence(paths: list[Path]) -> dict[str, list[Evidence]]:
    out: dict[str, list[Evidence]] = {name: [] for name, _ in COMPARE_CHECKS}
    for path in paths:
        text = _read_preview(path, max_chars=MAX_READ_CHARS).lower()
        for name, keywords in COMPARE_CHECKS:
            if any(k in text for k in keywords):
                detail = "; ".join(_line_hits(path, keywords, max_hits=2)) or "keyword match in file"
                out[name].append(Evidence(str(path), detail[:350]))
    return out


def rank_live_backtest_hypotheses() -> list[RankedHypothesis]:
    paths = _scan_trading_sources() + _collect_behavior_files()
    hypothesis_specs = (
        (
            "HIGH",
            "live/backtest bar selection may differ (last_closed_bar vs completed historical bars)",
            ("last_closed", "current_bar", "iloc[-1]", "iloc[-2]", "completed", "bar"),
            "If live evaluates an in-progress/last-closed bar differently from backtest, signals and entries diverge.",
            "Trace exact bar timestamp used in live report versus backtest row for the same symbol.",
            ["algo_scanner/backtest/fib_quality.py", "algo_scanner/strategy/real_algo.py", "services/live_paper_engine.py"],
            "Add a unit fixture with two bars and assert live/backtest choose the same bar.",
            0.90,
        ),
        (
            "HIGH",
            "execution path may be disabled or producing zero attempts",
            ("execution", "adapter", "n_execution_attempts", "disabled", "order", "paper"),
            "Signals can be valid while paper/live never attempts execution, causing live/backtest PnL mismatch.",
            "Inspect latest live report/state for execution_attempts and adapter status.",
            ["services/live_paper_engine.py", "services/live_dual_paper_cycle.py"],
            "Create a dry-run report fixture where one eligible signal must increment n_execution_attempts.",
            0.85,
        ),
        (
            "MEDIUM",
            "universe coverage differs between live and backtest",
            ("universe", "processed", "symbols", "tickers", "watchlist", "755", "738"),
            "Different symbols mean different ranking set and missing opportunities.",
            "Compare live processed symbol count to backtest universe file for the same date.",
            ["universe files", "reports/live_paper/dual", "backtest outputs"],
            "Assert report symbols are a subset/equal to configured universe for a small fixture.",
            0.75,
        ),
        (
            "MEDIUM",
            "risk cap or max open positions may block otherwise valid entries",
            ("max_open", "risk", "cap", "exposure", "position", "blocked", "reject"),
            "Backtest may assume free capacity while live portfolio state blocks entries.",
            "Inspect state/open positions plus risk settings at report timestamp.",
            ["services/portfolio_manager.py", "analytics/portfolio_engine.py", "reports/live_paper/state"],
            "Replay a fixture with max positions reached and verify block reason is explicit.",
            0.72,
        ),
        (
            "LOW",
            "slippage/spread/gap assumptions may differ",
            ("slippage", "spread", "gap", "commission", "fill"),
            "Execution assumptions affect fill price, stop/target hit order, and reported PnL.",
            "Compare backtest fill assumptions against live/paper fill model.",
            ["backtest outputs", "services/live_paper_engine.py"],
            "Add comparison fixture with spread/slippage and verify expected fill price.",
            0.55,
        ),
    )
    ranked: list[RankedHypothesis] = []
    for severity, title, keywords, why, verify, files, suggested_test, base_conf in hypothesis_specs:
        evidence = _collect_evidence(paths, keywords, limit=4)
        confidence = base_conf if evidence else max(0.30, base_conf - 0.25)
        ranked.append(
            RankedHypothesis(
                severity=severity,
                title=title,
                evidence=evidence,
                why=why,
                verify=verify,
                files=files,
                suggested_test=suggested_test,
                confidence=confidence,
            )
        )
    return sorted(ranked, key=lambda h: ({"HIGH": 3, "MEDIUM": 2, "LOW": 1}[h.severity], h.confidence), reverse=True)


def compare_live_vs_backtest() -> str:
    paths = _scan_trading_sources()
    evidence = _comparison_evidence(paths)
    lines = [
        "Live vs backtest comparison (read-only, no live execution).",
        f"Evidence roots: {TRADING_PROJECT_ROOT / 'reports' / 'live_paper'}, {TRADING_PROJECT_ROOT / 'reports' / 'live_paper_trials'}, backtest outputs",
        f"Files sampled: {len(paths)}",
        "",
        "Checks:",
    ]
    for name, _keywords in COMPARE_CHECKS:
        hits = evidence.get(name, [])
        status = "evidence found" if hits else "no direct evidence found"
        lines.append(f"- {name}: {status}")
        for hit in hits[:3]:
            lines.append(f"  evidence: {hit.path} :: {hit.detail}")
    lines.extend(["", "Ranked hypotheses:"])
    for i, hyp in enumerate(rank_live_backtest_hypotheses()[:5], 1):
        uncertainty = "" if hyp.evidence else " (hypothesis - local snippet not found)"
        lines.append(f"{i}. {hyp.severity} - {hyp.title}{uncertainty} confidence={hyp.confidence:.2f}")
        lines.extend(_format_evidence(hyp.evidence))
        lines.append(f"  why it matters: {hyp.why}")
        lines.append(f"  how to verify: {hyp.verify}")
        lines.append(f"  likely files: {', '.join(hyp.files)}")
        lines.append(f"  suggested test: {hyp.suggested_test}")
    lines.extend(
        [
            "",
            "Next actions:",
            "- Inspect the evidence files above.",
            "- Compare strategy config used by backtest vs live.",
            "- Propose a patch only after explicit approval.",
        ]
    )
    return "\n".join(lines)


def investigate_trading_mismatch() -> str:
    return "\n\n".join(
        [
            "Trading mismatch investigation (read-only).",
            compare_live_vs_backtest(),
            _section(
                "Focused Next Actions",
                [
                    "- inspect latest live report",
                    "- inspect latest backtest report",
                    "- search recent execution events for rejected/skipped/delayed entries",
                    "- verify universe/config/risk files against report timestamps",
                ],
            ),
        ]
    )


def trace_algorithm_behavior() -> str:
    paths = _collect_behavior_files()
    lines = [
        "Algorithm behavior trace (read-only)",
        f"Files checked: {len(paths)}",
    ]
    if not paths:
        lines.append(f"No expected behavior files found under {TRADING_PROJECT_ROOT}.")
        lines.append("Expected paths:")
        lines.extend(f"- {TRADING_PROJECT_ROOT / rel}" for rel in BEHAVIOR_FILES)
        return "\n".join(lines)
    for step, keywords in BEHAVIOR_STEPS:
        lines.append("")
        lines.append(f"Step: {step}")
        evidence = _collect_evidence(paths, keywords, limit=4)
        if evidence:
            lines.extend(_format_evidence(evidence))
        else:
            lines.append("  evidence: no local snippet found; behavior unknown")
        suspicious = []
        if step in {"entry gate", "delayed entry"}:
            suspicious.append("bar timing/live eligibility can diverge from backtest")
        if step in {"ranking", "portfolio cap", "position sizing"}:
            suspicious.append("ordering or state-dependent caps can change selected trades")
        if step == "paper/live decision":
            suspicious.append("execution adapter/disabled path can create zero-attempt reports")
        if suspicious:
            lines.append(f"  suspicious divergence points: {', '.join(suspicious)}")
    return "\n".join(lines)


def diff_live_and_backtest_logic() -> str:
    paths = _collect_behavior_files() + _scan_trading_sources()
    live_paths = [p for p in paths if any(k in str(p).lower() for k in ("live", "paper", "dual"))]
    backtest_paths = [p for p in paths if "backtest" in str(p).lower()]
    lines = [
        "Live/backtest logic diff (read-only)",
        f"Live-side files sampled: {len(live_paths)}",
        f"Backtest-side files sampled: {len(backtest_paths)}",
    ]
    for category, keywords in DIFF_CATEGORIES:
        live_ev = _collect_evidence(live_paths, keywords, limit=2)
        back_ev = _collect_evidence(backtest_paths, keywords, limit=2)
        if live_ev and back_ev:
            status = "same/needs detailed comparison"
            severity = "MEDIUM"
        elif live_ev or back_ev:
            status = "different"
            severity = "HIGH"
        else:
            status = "unknown"
            severity = "LOW"
        lines.append("")
        lines.append(f"- {category}: {status} severity={severity}")
        lines.extend(_format_evidence(live_ev + back_ev))
        lines.append(f"  next verification command: search investigation graph {category}")
    return "\n".join(lines)


def hunt_algorithm_bugs() -> str:
    paths = _collect_behavior_files()
    if not paths:
        paths = _iter_files(TRADING_PROJECT_ROOT, suffixes={".py"}, limit=250)
    issues: list[str] = ["Algorithm bug hunt (read-only; findings are hypotheses unless snippets prove behavior)."]
    found = 0
    for issue, severity, patterns, why in BUG_PATTERNS:
        regexes = [re.compile(p, re.I) for p in patterns]
        matched_issue = False
        for path in paths[:80]:
            text = _read_preview(path, max_chars=MAX_READ_CHARS)
            for line_no, line in enumerate(text.splitlines(), 1):
                if any(r.search(line) for r in regexes):
                    found += 1
                    matched_issue = True
                    issues.append(f"- {severity.upper()} issue: {issue}")
                    issues.append(f"  file path: {path}")
                    issues.append(f"  snippet: {path}:{line_no}: {line.strip()[:220]}")
                    issues.append(f"  why suspicious: {why}")
                    issues.append(f"  suggested test: add a focused fixture covering this branch in live and backtest modes")
                    break
            if matched_issue:
                break
    if found == 0:
        issues.append(f"No known bug patterns found in sampled files under {TRADING_PROJECT_ROOT}.")
    return "\n".join(issues[:90])


def propose_algorithm_patch() -> str:
    hypotheses = rank_live_backtest_hypotheses()
    top = hypotheses[0] if hypotheses else None
    problem = top.title if top else "No ranked hypothesis available; start with compare live vs backtest."
    files = top.files if top else ["unknown"]
    return "\n".join(
        [
            "Algorithm patch proposal (preview only - no files changed).",
            f"Problem: {problem}",
            f"Affected files: {', '.join(files)}",
            "Minimal diff (conceptual):",
            "```diff",
            "--- a/live_or_backtest_path.py",
            "+++ b/live_or_backtest_path.py",
            "@@",
            "- # implicit live/backtest decision or duplicated gate",
            "+ # centralize bar selection / entry gate / risk reason with explicit test coverage",
            "+ reason = explain_entry_decision(symbol, bar_timestamp, mode)",
            "+ record_decision_evidence(reason)",
            "```",
            "Tests to run:",
            "- py -3 -m py_compile <affected files>",
            "- py -3 -m pytest <targeted strategy/live/backtest tests> -q",
            "- small universe smoke test (dry run only)",
            "Rollback plan:",
            "- Revert the minimal diff for affected files only.",
            "- Restore prior config/report snapshots.",
            "Safety: preview only; use existing approved patch system before applying.",
        ]
    )


def plan_verification_run() -> str:
    return "\n".join(
        [
            "Verification run plan (commands only - not executed):",
            "1. Targeted unit tests:",
            "   py -3 -m pytest tests/test_phase45_investigation.py tests/test_phase46_investigation.py -q",
            "2. Compile changed Python files:",
            "   py -3 -m compileall algo_scanner services analytics local_jarvis",
            "3. Small universe smoke test (dry run only):",
            "   py -3 scripts/run_live_daily.py --dry-run --universe small",
            "4. Portfolio replay:",
            "   py -3 scripts/replay_portfolio.py --input reports/live_paper/state --dry-run",
            "5. Backtest/live comparison script:",
            "   py -3 scripts/compare_backtest_live.py --latest --no-trade",
            "6. Dashboard/report inspection:",
            "   open reports/live_paper/dual and reports/jarvis_investigations latest markdown",
            "Safety: do not execute live trading; ask explicitly before running any command.",
        ]
    )


def find_recent_code_changes() -> str:
    files: list[Path] = []
    for label, root in _project_roots():
        del label
        files.extend(_latest_files(root, suffixes=CODE_SUFFIXES, limit=30))
    files = sorted(set(files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:30]
    lines = ["Recent code/config changes (mtime evidence, read-only):"]
    for path in files[:20]:
        stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        lines.append(f"- {stamp} {path}")
    lines.append("Next actions: inspect changed files; compare against latest failing report.")
    return "\n".join(lines)


def propose_investigation_plan() -> str:
    return "\n".join(
        [
            "Phase 45 investigation plan (read-only first):",
            "1. inspect project - map roots, reports, configs, state.",
            "2. find failing tests - use pytest cache/terminal evidence, no broad test run.",
            "3. explain latest error - read latest terminal/report error evidence.",
            "4. inspect latest live report and latest backtest report.",
            "5. compare live vs backtest across signal, entry, ranking, risk, stale price, universe, config, data window, slippage, state.",
            "6. generate findings report with evidence paths and next actions.",
            "7. Only after explicit approval: propose/apply patches or run longer diagnostics.",
        ]
    )


def run_safe_diagnostics() -> str:
    lines = ["Safe diagnostics (read-only; no live trading; no arbitrary shell)."]
    lines.append(inspect_project())
    lines.append("")
    lines.append(find_failing_tests())
    lines.append("")
    lines.append("Next actions: explain latest error; generate findings report.")
    return "\n".join(lines)[:9000]


def generate_findings_report() -> str:
    hypotheses = rank_live_backtest_hypotheses()[:5]
    top_lines: list[str] = []
    evidence_rows: list[str] = ["| Severity | Hypothesis | Evidence |", "|---|---|---|"]
    for hyp in hypotheses:
        evidence_text = "; ".join(f"{ev.path}: {ev.detail}" for ev in hyp.evidence[:2])
        if not evidence_text:
            evidence_text = "No local snippet found; hypothesis only"
        top_lines.append(f"- {hyp.severity}: {hyp.title} (confidence={hyp.confidence:.2f})")
        evidence_rows.append(f"| {hyp.severity} | {hyp.title} | {evidence_text[:500]} |")
    risk = "HIGH" if any(h.severity == "HIGH" and h.evidence for h in hypotheses) else "MEDIUM"
    sections = [
        "# Phase 46 Findings Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "Safety: read-only; no live trading execution; no patch applied.",
        "",
        "## Executive Summary",
        "JARVIS scanned local project/trading evidence and ranked live-vs-backtest mismatch hypotheses. Claims with no snippet are marked as hypotheses, not facts.",
        "",
        "## Top 5 Root Causes",
        "\n".join(top_lines) if top_lines else "- No root causes ranked.",
        "",
        "## Evidence Table",
        "\n".join(evidence_rows),
        "",
        "## Risk Level",
        risk,
        "",
        "## Project",
        inspect_project(),
        "",
        "## Tests / Errors",
        find_failing_tests(),
        "",
        "## Trading Comparison",
        compare_live_vs_backtest(),
        "",
        "## Suggested Fixes",
        propose_algorithm_patch(),
        "",
        "## Verification Plan",
        plan_verification_run(),
        "",
        "## Open Questions",
        "- Which exact backtest report should be paired with the latest live/paper report?",
        "- Which universe/config snapshot was active for each run?",
        "- Are paper execution attempts expected to be enabled in this environment?",
        "",
        "## Files To Inspect Next",
        "\n".join(f"- {path}" for path in _specific_behavior_paths()),
        "",
        "## Next Actions",
        "- Select one finding and request a focused investigation.",
        "- Approve patching explicitly before any file changes.",
    ]
    body = "\n".join(sections)[:16000]
    PHASE46_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = PHASE46_REPORT_DIR / f"{ts}_findings.md"
    path.write_text(body, encoding="utf-8")
    return f"Findings report saved: {path}\n\n{body}"


def phase45_status() -> str:
    return "\n".join(
        [
            "Phase 45 status",
            "  Mode: Elite Code + Trading Investigation Engine",
            "  Runtime: console + HUD first; TTS optional/deferred",
            "  Safety: read-only by default; no live trading execution; no arbitrary shell",
            "  Commands:",
            "    - inspect project",
            "    - summarize current project",
            "    - find failing tests",
            "    - explain latest error",
            "    - investigate trading mismatch",
            "    - compare live vs backtest",
            "    - inspect latest live report",
            "    - inspect latest backtest report",
            "    - find recent code changes",
            "    - propose investigation plan",
            "    - run safe diagnostics",
            "    - generate findings report",
            "    - build investigation graph",
            "    - show investigation graph",
            "    - search investigation graph <query>",
            "    - trace algorithm behavior",
            "    - diff live and backtest logic",
            "    - hunt algorithm bugs",
            "    - propose algorithm patch",
            "    - plan verification run",
        ]
    )


def phase46_status() -> str:
    return "\n".join(
        [
            "Phase 46 status",
            "  Mode: Expert Algorithm Debugger + Trading Mismatch Investigator",
            "  Safety: read-only by default; no live trading execution; no arbitrary shell; preview-only patches",
            "  Evidence rule: claims cite local paths/snippets; uncertain items are hypotheses",
            "  New capabilities:",
            "    - investigation graph",
            "    - ranked root-cause hypotheses",
            "    - algorithm behavior trace",
            "    - live/backtest logic diff",
            "    - algorithm bug hunt",
            "    - patch proposal preview",
            "    - verification run planner",
            f"  Report path: {PHASE46_REPORT_DIR}",
        ]
    )
