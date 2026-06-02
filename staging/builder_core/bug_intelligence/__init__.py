"""Bug Intelligence subsystem (Phase 83).

Given a repository or a single source file, identify *likely bug locations*
and explain the reasoning. This is deterministic and AST/heuristic-based: no
LLM, no network. It never edits, fixes, or generates code for the target.

Public surface:
- ``analyzer.analyze_source`` / ``analyzer.analyze_repository``
- ``ranking.rank_reports`` / ``ranking.benchmark``
- ``findings.Finding``
- ``dataflow.analyze_source`` (Phase 86 — facts, not findings)
"""

from . import findings, patterns, analyzer, ranking, dataflow  # noqa: F401

__all__ = ["findings", "patterns", "analyzer", "ranking", "dataflow"]
