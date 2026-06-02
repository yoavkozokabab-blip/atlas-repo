"""Format ask results into benchmark JARVIS context packets."""

from __future__ import annotations

from typing import Any, Dict


def format_jarvis_packet(result: Dict[str, Any]) -> str:
    """Assemble the deterministic offline JARVIS context string."""
    lines = [
        f"MODE: {result.get('mode', 'unknown')}",
        "ANSWER:",
        str(result.get("answer", "")).strip(),
    ]
    evidence = result.get("evidence") or []
    if evidence:
        lines.append("EVIDENCE:")
        lines.extend(f"- {item}" for item in evidence[:12])
    sources = result.get("sources") or []
    if sources:
        lines.append("SOURCES:")
        lines.extend(f"- {item}" for item in sources[:12])
    quality = result.get("ask_quality") or {}
    if quality:
        lines.append("ASK_QUALITY:")
        for key in (
            "production_percent",
            "architecture_percent",
            "reports_percent",
            "benchmark_percent",
        ):
            lines.append(f"- {key}: {quality.get(key, 0)}")
    return "\n".join(lines).strip()
