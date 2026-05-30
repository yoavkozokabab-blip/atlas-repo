"""builder_core command-line interface.

Usage:
    py -3 -m builder_core.cli init     --project .
    py -3 -m builder_core.cli ask      "what are the biggest risks in this codebase?"
    py -3 -m builder_core.cli remember "we chose X because Y"
    py -3 -m builder_core.cli decisions

Local-only. Read-only except for files under <project>/.jarvis_builder/.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import (
    __version__,
    ask as ask_mod,
    benchmark as semantic_benchmark,
    decisions as dec_mod,
    indexer,
    risk,
    store,
)
from .bug_intelligence import analyzer as bug_analyzer, ranking as bug_ranking
from .bug_intelligence import security as bug_security
from .bug_intelligence import engine as bi_engine


def _add_project_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--project",
        default=".",
        help="Path to the target repository (default: current directory).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="builder_core",
        description="Standalone Builder Core CLI - local project intelligence.",
    )
    parser.add_argument("--version", action="version", version=f"builder_core {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Index a repository into .jarvis_builder/.")
    _add_project_arg(p_init)

    p_ask = sub.add_parser("ask", help="Ask a question about the indexed repository.")
    _add_project_arg(p_ask)
    p_ask.add_argument("question", help="The question to answer.")

    p_risk = sub.add_parser("risk-report", help="Rank suspicious Python files.")
    _add_project_arg(p_risk)
    p_risk.add_argument("--top", type=int, default=10, help="Maximum files to show.")

    p_remember = sub.add_parser("remember", help="Store a builder decision.")
    _add_project_arg(p_remember)
    p_remember.add_argument("text", help="The decision text, e.g. 'we chose X because Y'.")

    p_decisions = sub.add_parser("decisions", help="List stored decisions.")
    _add_project_arg(p_decisions)

    # --- Phase 83: Bug Intelligence ------------------------------------
    p_analyze = sub.add_parser(
        "analyze-file", help="Explain likely bug locations in a single source file.")
    _add_project_arg(p_analyze)
    p_analyze.add_argument("file", help="Path to the source file (relative to project or absolute).")

    p_scan = sub.add_parser(
        "bug-scan", help="Rank the most suspicious files across a repository.")
    _add_project_arg(p_scan)
    p_scan.add_argument("--top", type=int, default=10, help="Maximum files to list.")

    p_bench = sub.add_parser(
        "benchmark-quixbugs", help="Run the QuixBugs benchmark (if the dataset is present).")
    _add_project_arg(p_bench)
    p_bench.add_argument(
        "--engine", choices=["unified", "legacy"], default="unified",
        help="Which analysis path to measure (default: unified; legacy kept for comparison).")

    # --- Phase 89: security scan ---------------------------------------
    p_sec = sub.add_parser(
        "security-scan", help="Local taint-based security review across a repository.")
    _add_project_arg(p_sec)
    p_sec.add_argument("--top", type=int, default=20, help="Maximum findings to list.")

    return parser


def _cmd_init(project: str) -> int:
    project_root = store.resolve_project_root(project)
    index = indexer.build_index(project_root)
    path = store.save_index(project_root, index)
    stats = index["stats"]
    git = index["git"]

    print(f"Indexed project: {project_root}")
    print(f"  files: {stats['files']}  "
          f"(readme={stats['readme']}, docs={stats['docs']}, "
          f"src={stats['src']}, tests={stats['test']})")
    print(f"  chunks: {stats['chunks']}")
    project_type = index.get("project_type", {})
    print(f"  project type: {project_type.get('primary', 'unknown')}")
    print(f"  python analyzed: {len(index.get('python_analysis', []))}")
    if git.get("is_repo"):
        commit = (git.get('commit') or '')[:12]
        print(f"  git: branch={git.get('branch')} commit={commit} "
              f"log={len(index['git_log'])} commits")
    else:
        print("  git: not a repository (or git unavailable)")
    print(f"Index written to {path}")
    return 0


def _cmd_ask(project: str, question: str) -> int:
    project_root = store.resolve_project_root(project)
    index = store.load_index(project_root)
    if index is None:
        print("No index found. Run `init --project <path>` first.", file=sys.stderr)
        return 2

    result = ask_mod.answer(index, question)

    print("ANSWER")
    print(result["answer"])
    print()
    print("FINDINGS")
    if result["findings"]:
        for item in result["findings"]:
            print(f"- {item}")
    else:
        print("- (none)")
    print()
    print("EVIDENCE")
    if result["evidence"]:
        for item in result["evidence"]:
            print(f"- {item}")
    else:
        print("- (none)")
    print()
    print("SOURCES")
    if result["sources"]:
        for src in result["sources"]:
            print(f"- {src}")
    else:
        print("- (none)")
    return 0


def _cmd_risk_report(project: str, top: int) -> int:
    project_root = store.resolve_project_root(project)
    index = store.load_index(project_root)
    if index is None:
        print("No index found. Run `init --project <path>` first.", file=sys.stderr)
        return 2

    ranked = risk.rank_suspicious_files(index, top=max(0, top))
    print("RISK REPORT")
    if not ranked:
        print("No suspicious Python files detected.")
        return 0
    for position, item in enumerate(ranked, 1):
        print(
            f"{position}. [{item['severity'].upper()}] {item['path']} "
            f"score={item['score']} findings={len(item['findings'])}"
        )
        for finding in item["findings"][:5]:
            print(
                f"   - line {finding['line']}: {finding['rule']} - "
                f"{finding['message']}"
            )
    return 0


def _cmd_remember(project: str, text: str) -> int:
    project_root = store.resolve_project_root(project)
    try:
        record = dec_mod.remember(project_root, text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    commit = record.get("git_commit")
    commit_disp = commit[:12] if commit else "-"
    print("Decision stored.")
    print(f"  id:     {record['id']}")
    print(f"  topic:  {record['topic']}")
    print(f"  commit: {commit_disp}")
    print(f"  text:   {record['text']}")
    return 0


def _cmd_decisions(project: str) -> int:
    project_root = store.resolve_project_root(project)
    records = dec_mod.list_decisions(project_root)
    if not records:
        print("No decisions stored yet. Use `remember \"we chose X because Y\"`.")
        return 0
    print(f"{len(records)} decision(s):\n")
    for i, rec in enumerate(records, 1):
        date = rec.get("timestamp", "")[:10]
        topic = rec.get("topic", "general")
        commit = rec.get("git_commit")
        commit_disp = commit[:12] if commit else "-"
        print(f"{i}. [{date}] ({topic}) {commit_disp}")
        print(f"   {rec.get('text', '')}")
    return 0


def _severity_conf(finding) -> str:
    return f"{finding.severity.upper()} severity / {finding.confidence.upper()} confidence"


def _render_unified(index: int, f) -> None:
    loc = f"{f.function} " if f.function else ""
    print(f"{index}. [{f.severity.upper()}/{f.confidence.upper()}] {f.category}/{f.kind} "
          f"{f.rule} {loc}(line {f.line})  id={f.id}")
    print(f"   {f.title}")
    print(f"   why: {f.explanation}")
    print(f"   why this might be wrong: {f.why_might_be_wrong}")


def _cmd_analyze_file(project: str, file_arg: str) -> int:
    """Unified Builder Intelligence Engine — single file."""
    project_root = store.resolve_project_root(project)
    result = bi_engine.analyze_file(file_arg, project_root=project_root)
    if result is None:
        print(f"File not found or unreadable under project: {file_arg}", file=sys.stderr)
        return 2
    print(bi_engine.format_result(result))
    return 0


def _cmd_bug_scan(project: str, top: int) -> int:
    """Unified engine — rank suspicious files (consistent section format)."""
    project_root = store.resolve_project_root(project)
    results = bi_engine.analyze_repository(project_root)
    ranked = bi_engine.rank_files(results, top=top)

    print("SUMMARY")
    if not ranked:
        print(f"{project_root}: no suspicious files detected.")
        print("\nFINDINGS\n- (none)\n\nEVIDENCE\n- (none)\n"
              "\nSOURCES\n- (none)\n\nNEXT VERIFICATION STEPS\n- (none)")
        return 0
    print(f"{len(ranked)} suspicious file(s). Most suspicious: {ranked[0].file} "
          f"(score={ranked[0].score}).")
    print()
    print("FINDINGS")
    for i, r in enumerate(ranked, 1):
        tf = r.findings[0]
        print(f"{i}. {r.file}  (score={r.score}, findings={len(r.findings)})")
        print(f"   lead: [{tf.severity.upper()}/{tf.confidence.upper()}] "
              f"{tf.category}/{tf.kind} {tf.rule} @ line {tf.line}  id={tf.id}")
    print()
    print("EVIDENCE")
    for r in ranked:
        tf = r.findings[0]
        print(f"- {r.file}:{tf.line}: {tf.evidence or '(structural - see line)'}")
    print()
    print("SOURCES")
    for r in ranked:
        print(f"- {r.file}")
    print()
    print("NEXT VERIFICATION STEPS")
    for r in ranked:
        tf = r.findings[0]
        print(f"- [{tf.id}] {tf.next_verification_step}")
    return 0


def _cmd_security_scan(project: str, top: int) -> int:
    """Unified engine — security findings only, ranked."""
    project_root = store.resolve_project_root(project)
    findings = bi_engine.security_findings(project_root, top=top)

    print("SECURITY SCAN")
    print("SUMMARY")
    if not findings:
        print("No high-confidence security findings detected.")
        print("\nFINDINGS\n- (none)\n\nEVIDENCE\n- (none)\n"
              "\nSOURCES\n- (none)\n\nNEXT VERIFICATION STEPS\n- (none)")
        return 0
    files = sorted({f.file for f in findings})
    by_rule: dict = {}
    for f in findings:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    print(f"{len(findings)} finding(s) across {len(files)} file(s). "
          + ", ".join(f"{k}={v}" for k, v in sorted(by_rule.items())))
    print()
    print("FINDINGS")
    for i, f in enumerate(findings, 1):
        _render_unified(i, f)
    print()
    print("EVIDENCE")
    for f in findings:
        print(f"- {f.file}:{f.line}: {f.evidence or '(see line)'}")
    print()
    print("SOURCES")
    for path in files:
        print(f"- {path}")
    print()
    print("NEXT VERIFICATION STEPS")
    for f in findings:
        print(f"- [{f.id}] {f.next_verification_step}")
    return 0


def _cmd_benchmark_quixbugs(project: str, engine_mode: str = "unified") -> int:
    project_root = store.resolve_project_root(project)
    if engine_mode == "legacy":
        result = semantic_benchmark.evaluate_quixbugs(project_root)
        print(semantic_benchmark.format_report(result))
    else:
        from .bug_intelligence import engine_benchmark
        result = engine_benchmark.evaluate_quixbugs_engine(project_root)
        print(engine_benchmark.format_report(result))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _cmd_init(args.project)
    if args.command == "ask":
        return _cmd_ask(args.project, args.question)
    if args.command == "risk-report":
        return _cmd_risk_report(args.project, args.top)
    if args.command == "remember":
        return _cmd_remember(args.project, args.text)
    if args.command == "decisions":
        return _cmd_decisions(args.project)
    if args.command == "analyze-file":
        return _cmd_analyze_file(args.project, args.file)
    if args.command == "bug-scan":
        return _cmd_bug_scan(args.project, args.top)
    if args.command == "benchmark-quixbugs":
        return _cmd_benchmark_quixbugs(args.project, getattr(args, "engine", "unified"))
    if args.command == "security-scan":
        return _cmd_security_scan(args.project, args.top)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
