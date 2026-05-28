"""Auto-tune voice settings from local diagnostics (Phase 42 v2)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from voice.auto_tune import (
    analyze_voice_diagnostics,
    apply_safe_env_recommendations,
    format_auto_tune_report,
)


class AutoTuneVoiceAction(BaseAction):
    intent = Intent.AUTO_TUNE_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        text = (request.raw_text or "").lower()
        apply = "apply" in text
        recs = analyze_voice_diagnostics()
        if apply:
            applied = apply_safe_env_recommendations(recs)
            summary = format_auto_tune_report(apply=True)
            if applied:
                summary += "\nUpdated:\n" + "\n".join(f"  {line}" for line in applied)
            else:
                summary += "\nNo .env changes written."
            return result_success(
                Intent.AUTO_TUNE_VOICE,
                summary,
                data={"applied": applied, "recommendations": [r.__dict__ for r in recs]},
            )
        return result_success(
            Intent.AUTO_TUNE_VOICE,
            format_auto_tune_report(apply=False),
            data={"recommendations": [r.__dict__ for r in recs]},
        )
