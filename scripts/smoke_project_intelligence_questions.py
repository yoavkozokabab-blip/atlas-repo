"""Smoke: Phase 80 Project Intelligence — 10 builder questions end-to-end."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

QUESTIONS = [
    "Why was Phase 73A built?",
    "What problem does Phase 79 solve?",
    "What are the biggest architectural risks in the current JARVIS codebase?",
    "What should be built next and why?",
    "Summarize the current state of the project in under 500 words.",
    "What are the most important unfinished phases?",
    "What changed in the last 30 days?",
    "What decisions were made recently that could affect future architecture?",
    "If a new developer joined today, what would they need to understand first?",
    "What parts of the codebase appear unrelated to Jarvis for Builders?",
]

CONTAMINATION = ("FINAL_ALGO_TRADER", "algo_trader", "live_paper", "scheduled_logs")


def main() -> int:
    os.environ.setdefault("LLM_TOOL_ROUTER_ENABLED", "false")
    os.environ.setdefault("LLM_TOOL_ROUTER_SHADOW", "false")

    from actions.registry import ActionRegistry
    from brain.intent_classifier import classify
    from core.types import Intent
    from project_intelligence.engine import answer_question

    ok = True
    registry = ActionRegistry()
    results: list[dict] = []

    for question in QUESTIONS:
        req = classify(question)
        if req.intent != Intent.ANSWER_PROJECT_QUESTION:
            print(f"FAIL routing {question!r} -> {req.intent.value}")
            ok = False
            continue

        result = answer_question(question)
        text = result.summary or ""
        blob = text.lower()
        if "could not understand" in blob:
            print(f"FAIL answer blocked for {question!r}")
            ok = False
            continue
        if any(bad.lower() in blob for bad in CONTAMINATION):
            print(f"FAIL contamination in answer for {question!r}")
            ok = False
            continue
        if "project intelligence" not in blob and "parts of the jarvis codebase" not in blob:
            print(f"FAIL missing analyst header for {question!r}")
            ok = False
            continue

        exec_result = registry.execute(req.model_copy(update={"params": {"query": question}}))
        if exec_result.intent == Intent.UNKNOWN:
            print(f"FAIL registry execute unknown for {question!r}")
            ok = False
            continue

        print(f"OK {question[:60]}...")
        results.append(
            {
                "question": question,
                "intent": req.intent.value,
                "confidence": req.confidence,
                "classifier_source": req.classifier_source,
                "summary_preview": text[:400],
                "evidence_files": result.data.get("evidence_files", []),
            }
        )

    out_path = _ROOT / "reports" / "phase80_smoke_samples.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote sample previews to {out_path}")

    print("SMOKE PASS phase80_project_intelligence" if ok else "SMOKE FAIL phase80_project_intelligence")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
