"""Security MVP (Phase 89): local, read-only taint review.

Consumes the value-flow facts from ``valueflow`` and turns high-confidence
source->sink observations into findings. This is *static local code review*
only: no execution, no payloads, no network, no scanning of remote systems.

Categories supported:
  - code_injection           eval / exec on tainted input
  - command_injection        subprocess/os.system tainted or shell=True
  - sql_injection            SQL string built from tainted input then executed
  - path_traversal           open() on a tainted, unsanitized path
  - unsafe_deserialization   pickle/marshal load of tainted data; yaml.load unsafe
  - weak_crypto              md5 / sha1 usage
  - null_dereference         (value finding) dereference of a maybe-None value

Every finding carries: id, severity, confidence, category, file, line,
explanation, evidence, why_might_be_wrong, next_verification_step.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import valueflow

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


@dataclass
class Finding89:
    category: str
    severity: str
    confidence: str
    file: str
    line: int
    explanation: str
    evidence: str
    why_might_be_wrong: str
    next_verification_step: str
    kind: str = "security"  # "security" | "value"
    id: str = ""

    def __post_init__(self):
        if not self.id:
            digest = hashlib.sha1(
                f"{self.category}|{self.file}|{self.line}".encode("utf-8")
            ).hexdigest()[:8]
            prefix = "SEC" if self.kind == "security" else "VAL"
            self.id = f"{prefix}-{self.category[:4].upper()}-{digest}"

    @property
    def weight(self) -> float:
        return SEVERITY_WEIGHT.get(self.severity, 1) * CONFIDENCE_WEIGHT.get(self.confidence, 0.3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "category": self.category, "severity": self.severity,
            "confidence": self.confidence, "file": self.file, "line": self.line,
            "explanation": self.explanation, "evidence": self.evidence,
            "why_might_be_wrong": self.why_might_be_wrong,
            "next_verification_step": self.next_verification_step, "kind": self.kind,
        }


@dataclass
class SecurityReport:
    file: str
    findings: List[Finding89] = field(default_factory=list)       # security
    value_findings: List[Finding89] = field(default_factory=list)  # null-deref etc.
    sources: List[str] = field(default_factory=list)

    @property
    def all_findings(self) -> List[Finding89]:
        return self.findings + self.value_findings


# ---------------------------------------------------------------------------
# Observation -> finding mapping (high-confidence only)
# ---------------------------------------------------------------------------
def _sink_to_finding(obs: Dict[str, Any], file: str) -> Finding89 | None:
    cat = obs["category"]
    line = obs["line"]
    ev = obs.get("evidence", "")
    tainted = obs.get("tainted", False)
    shell_true = obs.get("shell_true", False)
    sanitized = obs.get("sanitized", False)

    if cat == "code_injection" and tainted:
        return Finding89(
            category=cat, severity="critical", confidence="high", file=file, line=line,
            explanation=(
                f"`{obs['callee']}(...)` is called on a value that data-flow analysis "
                f"traced back to untrusted input. Untrusted data reaching eval/exec is "
                f"arbitrary code execution."
            ),
            evidence=ev,
            why_might_be_wrong=(
                "The value may have been validated or constrained on a path the "
                "intraprocedural analysis cannot see (e.g. an allow-list in a caller)."
            ),
            next_verification_step=(
                "Trace the argument to its origin and confirm it cannot be influenced "
                "by an external caller; if it can, replace eval/exec with a safe parser "
                "or an explicit dispatch table."
            ),
        )
    if cat == "command_injection" and (tainted or shell_true):
        why_shell = " with shell=True" if shell_true else ""
        return Finding89(
            category=cat, severity="high", confidence="high", file=file, line=line,
            explanation=(
                f"`{obs['callee']}` runs an OS command{why_shell}"
                + (" using a value traced from untrusted input." if tainted else
                   "; shell=True invokes a shell that interprets metacharacters.")
            ),
            evidence=ev,
            why_might_be_wrong=(
                "The command/args may be fully constant or built only from trusted "
                "constants; shell=True is occasionally required and otherwise constrained."
            ),
            next_verification_step=(
                "Confirm whether any argument is externally controllable. Prefer a list "
                "argv with shell=False; if a shell is required, shlex.quote untrusted parts."
            ),
        )
    if cat == "sql_injection" and tainted:
        return Finding89(
            category=cat, severity="high", confidence="high", file=file, line=line,
            explanation=(
                "A SQL string passed to execute() was built from untrusted input via "
                "string construction (concatenation / f-string / %), not bound parameters."
            ),
            evidence=ev,
            why_might_be_wrong=(
                "The interpolated value might be a server-side constant or already "
                "escaped; some drivers accept pre-built statements safely."
            ),
            next_verification_step=(
                "Check whether the interpolated value is user-controllable; if so, switch "
                "to a parameterized query (execute(sql, params)) and remove string building."
            ),
        )
    if cat == "path_traversal" and tainted and not sanitized:
        return Finding89(
            category=cat, severity="medium", confidence="medium", file=file, line=line,
            explanation=(
                "open() receives a path traced from untrusted input with no obvious "
                "normalization (e.g. basename / allow-list). A '../' sequence could "
                "escape the intended directory."
            ),
            evidence=ev,
            why_might_be_wrong=(
                "The path may be validated elsewhere, or user-chosen paths may be an "
                "intended feature (e.g. a CLI that opens a file the user names)."
            ),
            next_verification_step=(
                "Confirm the path is confined to an allowed root (os.path.realpath + "
                "prefix check) before opening, or restrict to a basename within a fixed dir."
            ),
        )
    if cat == "unsafe_deserialization":
        deser = obs.get("deser", "")
        if deser == "pickle" and tainted:
            return Finding89(
                category=cat, severity="high", confidence="high", file=file, line=line,
                explanation=(
                    f"`{obs['callee']}` deserializes data traced from an untrusted source. "
                    "pickle/marshal execute arbitrary objects during load."
                ),
                evidence=ev,
                why_might_be_wrong=(
                    "The data source may actually be trusted (an internal cache the "
                    "attacker cannot write)."
                ),
                next_verification_step=(
                    "Confirm the byte source cannot be attacker-influenced; if it can, use "
                    "a safe format (json) or a signed/validated container."
                ),
            )
        if deser == "yaml" and not sanitized:
            return Finding89(
                category=cat, severity="high", confidence="medium", file=file, line=line,
                explanation=(
                    "yaml.load() without an explicit safe Loader can instantiate arbitrary "
                    "Python objects from the document."
                ),
                evidence=ev,
                why_might_be_wrong=(
                    "Input may be a trusted, developer-authored file rather than external."
                ),
                next_verification_step=(
                    "Replace with yaml.safe_load (or Loader=yaml.SafeLoader) unless arbitrary "
                    "tag construction is genuinely required and the input is trusted."
                ),
            )
        return None
    if cat == "weak_crypto":
        algo = obs.get("algo", "md5/sha1")
        return Finding89(
            category=cat, severity="medium", confidence="medium", file=file, line=line,
            explanation=(
                f"`{algo}` is cryptographically weak (collisions / preimage weaknesses) and "
                "should not be used for passwords, signatures, or integrity of security tokens."
            ),
            evidence=ev,
            why_might_be_wrong=(
                "It may be used for a non-security purpose (cache key, checksum of "
                "non-adversarial data), where weakness is harmless."
            ),
            next_verification_step=(
                "Confirm the hash is not protecting a security boundary; if it is, move to "
                "SHA-256+ (or a password KDF like bcrypt/argon2 for credentials)."
            ),
        )
    return None


def _value_to_finding(vf: Dict[str, Any], file: str) -> Finding89:
    var = vf.get("var", "value")
    state = vf.get("null_state", "maybe_none")
    return Finding89(
        category="null_dereference", severity="medium",
        confidence="high" if state == "definitely_none" else "medium",
        file=file, line=vf["line"],
        explanation=(
            f"`{var}` may be None on this path ({state}) but is dereferenced here "
            f"without a preceding None check on every path that reaches it."
        ),
        evidence=vf.get("evidence", ""),
        why_might_be_wrong=(
            "A caller may guarantee a non-None argument, or a guard may exist in a form "
            "the intraprocedural analysis did not recognize."
        ),
        next_verification_step=(
            f"Confirm whether `{var}` can be None at this point; if so, add an explicit "
            f"guard or default before the dereference."
        ),
        kind="value",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze_source(text: str, rel_path: str = "<source>") -> SecurityReport:
    facts = valueflow.analyze_source(text, rel_path)
    report = SecurityReport(file=rel_path)
    seen_src: set = set()
    for fn in facts.get("functions", []):
        for obs in fn.get("sink_observations", []):
            finding = _sink_to_finding(obs, rel_path)
            if finding is not None:
                report.findings.append(finding)
        for vf in fn.get("value_findings", []):
            report.value_findings.append(_value_to_finding(vf, rel_path))
        for src in fn.get("source_observations", []):
            label = f"line {src['line']}: {src['kind']} ({src['name']})"
            if label not in seen_src:
                seen_src.add(label)
                report.sources.append(label)
    # rank security findings strongest first
    report.findings.sort(key=lambda f: (-f.weight, f.line))
    return report


def analyze_path(abs_path: str, rel_path: str) -> SecurityReport:
    try:
        with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return SecurityReport(file=rel_path)
    return analyze_source(text, rel_path)


def scan_repository(root: str, top: int = 20) -> List[Finding89]:
    """Walk a repo (read-only) and return the strongest security findings."""
    from .analyzer import collect_python_files  # reuse the existing safe walker

    findings: List[Finding89] = []
    for abs_path, rel_path in collect_python_files(root):
        report = analyze_path(abs_path, rel_path)
        findings.extend(report.findings)
    findings.sort(key=lambda f: (-f.weight, f.file, f.line))
    return findings[: max(0, top)]
