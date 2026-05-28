#!/usr/bin/env python3
"""Phase 67 — balance weak categories and emit before/after report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

PHASE67_TARGETS = {
    "Voice Conversation": 50.0,
    "Integrations (Email/Calendar)": 40.0,
    "Desktop Operator": 80.0,
    "Recovery After Failures": 80.0,
    "Multi-Step Task Completion": 85.0,
}

BEFORE_BASELINE = {
    "Voice Conversation": 0.0,
    "Integrations (Email/Calendar)": 0.0,
    "Desktop Operator": 68.0,
    "Recovery After Failures": 70.0,
    "Multi-Step Task Completion": 80.0,
}


def _ensure_voice_prompt_wav() -> None:
    prompt = _ROOT / "data" / "voice_evidence" / "validation_prompt.wav"
    if prompt.is_file():
        return
    prompt.parent.mkdir(parents=True, exist_ok=True)
    try:
        import asyncio

        import edge_tts

        async def _gen() -> None:
            comm = edge_tts.Communicate("show voice health", voice="en-US-GuyNeural")
            await comm.save(str(prompt))

        asyncio.run(_gen())
    except Exception:
        pass


def _load_before() -> dict[str, float]:
    raw_path = _ROOT / "reports" / "phase66_strict_validation_raw.json"
    if not raw_path.is_file():
        return dict(BEFORE_BASELINE)
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        out = dict(BEFORE_BASELINE)
        for cat in data.get("categories", []):
            name = cat.get("category", "")
            if name in out:
                out[name] = float(cat.get("real_success_rate", out[name]))
        return out
    except Exception:
        return dict(BEFORE_BASELINE)


def _write_balance_report(before: dict[str, float], after: dict[str, float]) -> Path:
    lines = [
        "# Phase 67 Balance Report",
        "",
        "Targets: Voice 50%, Integrations 40%, Desktop 80%, Recovery 80%, Multi-step 85%.",
        "",
        "## Before / After (real_success_rate %)",
        "",
        "| Category | Before | After | Target | Met |",
        "|----------|--------|-------|--------|-----|",
    ]
    for cat, target in PHASE67_TARGETS.items():
        b = before.get(cat, 0.0)
        a = after.get(cat, 0.0)
        met = "yes" if a >= target else "no"
        lines.append(f"| {cat} | {b} | {a} | {target} | {met} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Primary score remains **real_success_rate** only (Phase 66.1 strict rules).",
            "- Voice real tests require mic capture + STT + routing + TTS with evidence JSON.",
            "- Integrations readonly mode uses `gmail_readonly` / `gcal_readonly` fixture providers.",
            "- Desktop OCR uses tesseract → Windows OCR → accessibility fallback chain.",
            "",
        ]
    )
    path = _ROOT / "reports" / "phase67_balance_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    _ensure_voice_prompt_wav()
    before = _load_before()

    import config

    config.INTEGRATIONS_EMAIL_MODE = "gmail_readonly"
    config.INTEGRATIONS_CALENDAR_MODE = "gcal_readonly"

    from validation.run_all_strict import run_all_strict_validations
    from validation.strict_framework import write_strict_real_world_report

    measurements = run_all_strict_validations()
    write_strict_real_world_report(measurements)

    after = {m.category: m.real_success_rate for m in measurements}
    report_path = _write_balance_report(before, after)

    print(f"Wrote {report_path}")
    print(f"Wrote {_ROOT / 'reports' / 'strict_real_world_validation_report.md'}")
    print(f"Wrote {_ROOT / 'reports' / 'phase66_strict_validation_raw.json'}")

    failed = [c for c, t in PHASE67_TARGETS.items() if after.get(c, 0.0) < t]
    if failed:
        print("\nBelow target:")
        for c in failed:
            print(f"  - {c}: {after.get(c, 0.0)}% (target {PHASE67_TARGETS[c]}%)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
