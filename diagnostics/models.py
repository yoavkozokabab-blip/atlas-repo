"""Structured diagnostic output models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class DiagnosticFinding:
    """One correlated issue from a data source."""

    source: str
    issue: str
    evidence: list[str] = field(default_factory=list)
    severity: str = "medium"
    likely_cause: str = ""
    suggested_steps: list[str] = field(default_factory=list)

    def score(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 5)


@dataclass
class DiagnosticReport:
    """Aggregated read-only diagnostic result."""

    top_issue: str
    findings: list[DiagnosticFinding] = field(default_factory=list)
    summary: str = ""
    sources_checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_issue": self.top_issue,
            "summary": self.summary,
            "sources_checked": self.sources_checked,
            "findings": [
                {
                    "source": f.source,
                    "issue": f.issue,
                    "evidence": f.evidence,
                    "severity": f.severity,
                    "likely_cause": f.likely_cause,
                    "suggested_steps": f.suggested_steps,
                }
                for f in self.findings
            ],
        }

    @classmethod
    def from_findings(
        cls,
        findings: list[DiagnosticFinding],
        *,
        sources_checked: list[str],
        title: str = "Diagnostics",
    ) -> "DiagnosticReport":
        ranked = sorted(findings, key=lambda f: f.score())
        top = ranked[0].issue if ranked else "No significant issues detected."
        lines = [f"{title} — top issue: {top}"]
        if ranked:
            lines.append("")
            for i, f in enumerate(ranked[:8], 1):
                lines.append(f"{i}. [{f.severity.upper()}] {f.issue} ({f.source})")
                if f.evidence:
                    lines.append(f"   Evidence: {f.evidence[0]}")
                    for ev in f.evidence[1:3]:
                        lines.append(f"             {ev}")
                if f.likely_cause:
                    lines.append(f"   Likely cause: {f.likely_cause}")
                if f.suggested_steps:
                    lines.append(f"   Next steps: {f.suggested_steps[0]}")
        else:
            lines.append("All checked sources look normal (read-only scan).")
        return cls(
            top_issue=top,
            findings=ranked,
            summary="\n".join(lines),
            sources_checked=sources_checked,
        )
