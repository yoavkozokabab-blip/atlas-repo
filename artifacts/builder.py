"""Phase 29 — presentations and documents (safe outputs under reports/artifacts)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from config import ARTIFACTS_DIR


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50] or "topic"


def build_presentation_outline(topic: str) -> tuple[Path, str]:
    slug = _slug(topic)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = ARTIFACTS_DIR / "presentations"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"presentation_{slug}_{ts}.md"
    body = f"""# Presentation: {topic.strip() or 'Untitled'}

## Slide 1 — Title
{topic.strip() or 'Overview'}

## Slide 2 — Context
- Problem statement
- Audience goals

## Slide 3 — Key points
- Point A
- Point B
- Point C

## Slide 4 — Evidence
- Metrics / logs (read-only references)
- Risks and mitigations

## Slide 5 — Next steps
- Supervised tasks
- Experiments (approval required)

_Output only — no auto PowerPoint binary in Phase 29 MVP._
"""
    path.write_text(body, encoding="utf-8")
    return path, body


def create_report_document(topic: str) -> tuple[Path, str]:
    slug = _slug(topic)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = ARTIFACTS_DIR / "documents"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report_{slug}_{ts}.md"
    body = f"""# Report: {topic.strip() or 'General'}

Generated: {datetime.now(timezone.utc).isoformat()}

## Summary

(Expand after supervised task findings.)

## Findings

- Link to `show task findings` output

## Recommendations

1. Review evidence
2. Propose patch if needed (preview only)
3. Approve before apply

"""
    path.write_text(body, encoding="utf-8")
    return path, body


def create_study_summary(topic: str) -> tuple[Path, str]:
    path, body = create_report_document(f"Study: {topic}")
    study_path = path.parent / path.name.replace("report_", "study_")
    study_path.write_text(body.replace("# Report:", "# Study summary:"), encoding="utf-8")
    return study_path, study_path.read_text(encoding="utf-8")
