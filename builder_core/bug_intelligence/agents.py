"""Deterministic pipeline-stage components for the Builder Intelligence Engine.

These are NOT autonomous agents. They are named, single-responsibility stages
of one local analysis pipeline. None of them executes external actions, calls a
network, runs the analyzed code, or modifies any file. Each only reads source
text / facts and returns data.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from . import facts as facts_mod
from . import finding as finding_mod
from . import patterns, security
from .finding import Finding


class ParseAgent:
    """source text -> AST module (errors captured, never raised to caller)."""

    def parse(self, text: str, path: str) -> Tuple[Optional[ast.AST], List[str]]:
        try:
            return ast.parse(text), []
        except SyntaxError as exc:
            return None, [f"{type(exc).__name__}: {exc.msg} (line {exc.lineno})"]


class DataFlowAgent:
    """Thin owner of the data-flow facts (loops, container mutations)."""

    def facts(self, text: str, path: str):
        from . import dataflow
        return dataflow.analyze_source(text, path)


class ValueFlowAgent:
    """Thin owner of the value-flow facts (CFG, reaching defs, nullability,
    intervals, taint)."""

    def facts(self, text: str, path: str):
        from . import valueflow
        return valueflow.analyze_source(text, path)


class FactExtractionAgent:
    """Combines data-flow + value-flow + test expectations into one fact model."""

    def extract(self, text: str, path: str,
                test_documents: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        return facts_mod.extract_module_facts(text, path, test_documents=test_documents)


class LogicBugAgent:
    """Logic / algorithm-structure / maintainability / test-gap findings.

    Reuses the audited pattern + data-flow detectors (`patterns.run_all`), which
    already consume data-flow facts where it matters (e.g.
    unguarded_container_consumption), and maps them onto the unified schema.
    """

    def run(self, tree: ast.AST, lines: List[str], file: str) -> List[Finding]:
        stem = file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        out: List[Finding] = []
        for pf in patterns.run_all(tree, lines, stem):
            out.append(finding_mod.from_pattern_finding(pf, file))
        return out


class FactLogicAgent:
    """Fact-backed logic findings (Phase 92B): detectors that consume the unified
    fact model instead of re-walking the AST. Currently: inconsistent_return."""

    def run(self, module_facts: Dict[str, Any], file: str) -> List[Finding]:
        from . import fact_detectors
        return fact_detectors.all_detectors(module_facts, file)


class InterproceduralAgent:
    """Phase 93A — infrastructure only. Attaches an ``interproc`` section
    (ephemeral same-file call graph + bounded function summaries) to the fact
    model. It emits NO findings and is consumed by NO detector. Removing its one
    registration in engine._fact_augmenters fully disables it with no behavior
    change (the call graph and summaries simply stop being attached)."""

    def attach(self, module_facts: Dict[str, Any], tree, file: str) -> Dict[str, Any]:
        try:
            from . import callgraph, summaries
            cg = callgraph.build_call_graph(tree, file)
            summ = summaries.compute_summaries(module_facts, cg)
            module_facts["interproc"] = {"call_graph": cg, "summaries": summ}
        except Exception:
            module_facts.setdefault("interproc", {})
        return module_facts


class SecurityAgent:
    """Taint-based security findings + value-level null-deref, via valueflow."""

    def run(self, text: str, file: str) -> List[Finding]:
        report = security.analyze_source(text, file)
        out: List[Finding] = []
        for sf in report.findings:
            out.append(finding_mod.from_security_finding(sf, file))
        for vf in report.value_findings:
            out.append(finding_mod.from_security_finding(vf, file))
        return out


class AlgorithmAgent:
    """Algorithm-correctness findings from the semantic invariant detectors.

    The legacy semantic reasoning is wrapped here as one detector source of the
    unified engine (algorithm_bug category) rather than a separate engine.
    """

    def run(self, tree: ast.AST, text: str, file: str,
            test_documents: Optional[List[Dict[str, str]]] = None) -> List[Finding]:
        try:
            from .. import semantic_reasoning
            result = semantic_reasoning.analyze_semantics(
                tree, file, text, test_documents=test_documents or [])
        except Exception:
            return []
        return [finding_mod.from_semantic_finding(d, file) for d in result.get("findings", [])]


class FindingRankerAgent:
    """Dedupe + rank findings by severity x confidence."""

    def rank(self, findings: List[Finding]) -> List[Finding]:
        return finding_mod.rank(findings)


class EvidenceFormatterAgent:
    """Render an AnalysisResult into the unified CLI sections."""

    def format_file(self, result) -> str:
        f = result
        lines: List[str] = []
        cats: Dict[str, int] = {}
        for fd in f.findings:
            cats[fd.category] = cats.get(fd.category, 0) + 1
        cat_summary = ", ".join(f"{k}={v}" for k, v in sorted(cats.items())) or "no findings"

        lines.append("SUMMARY")
        if f.errors:
            lines.append(f"{f.file}: parse error ({'; '.join(f.errors)}).")
        else:
            top = f.findings[0] if f.findings else None
            head = (f"{f.file}: {len(f.functions)} function(s), {len(f.findings)} finding(s) "
                    f"[{cat_summary}].")
            if top:
                head += f" Top: {top.title} ({top.severity}/{top.confidence})."
            lines.append(head)
        lines.append("")

        lines.append("FINDINGS")
        if f.findings:
            for i, fd in enumerate(f.findings, 1):
                loc = f"{fd.function} " if fd.function else ""
                lines.append(f"{i}. [{fd.severity.upper()}/{fd.confidence.upper()}] "
                             f"{fd.category}/{fd.kind} {fd.rule} {loc}(line {fd.line})  id={fd.id}")
                lines.append(f"   {fd.title}")
                lines.append(f"   why: {fd.explanation}")
                lines.append(f"   why this might be wrong: {fd.why_might_be_wrong}")
        else:
            lines.append("- (none)")
        lines.append("")

        lines.append("EVIDENCE")
        if f.findings:
            for fd in f.findings:
                ev = fd.evidence or "(structural - see line)"
                facts = f"  [{', '.join(fd.source_facts)}]" if fd.source_facts else ""
                lines.append(f"- {fd.file}:{fd.line}: {ev}{facts}")
        else:
            lines.append("- (none)")
        lines.append("")

        lines.append("SOURCES")
        srcs = result.metadata.get("taint_sources", [])
        if srcs:
            for s in srcs:
                lines.append(f"- {s}")
        else:
            lines.append(f"- {f.file} (no untrusted-input sources detected)")
        lines.append("")

        lines.append("NEXT VERIFICATION STEPS")
        if f.findings:
            for fd in f.findings:
                lines.append(f"- [{fd.id}] {fd.next_verification_step}")
        else:
            lines.append("- No findings to verify.")
        return "\n".join(lines)
