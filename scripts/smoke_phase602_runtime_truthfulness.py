"""Integrated runtime smoke for Phase 60.2 truthfulness checks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_command(intent_name: str, text: str):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    intent = getattr(Intent, intent_name)
    reg = ActionRegistry()
    action = reg._actions.get(intent.value)
    assert action is not None, f"{intent.value} action missing"
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    import config as cfg
    from core.env_precedence import format_runtime_config_mismatches
    from memory.store import get_personal_memory
    from voice.audio_status import set_selected_verified_audio_backend

    # startup + streaming truth
    mismatches = format_runtime_config_mismatches()
    assert "Runtime config mismatches" in mismatches
    assert isinstance(cfg.STT_STREAMING_BUFFER_ENABLED, bool)

    # memory
    mem = get_personal_memory()
    mem.remember("phase602 smoke memory", category="temporary_fact", ttl_seconds=120)
    assert mem.list_visible(limit=10)

    # summaries and browser utilities
    day = _run_command("SUMMARIZE_MY_DAY", "summarize my day")
    assert "MOCK MODE" in day.summary
    browser = _run_command("SHOW_BROWSER_DEBUG", "show browser debug")
    assert "MOCK MODE" in browser.summary
    search = _run_command("SEARCH_WEB_FOR", "search web for runtime truthfulness")
    assert "MOCK MODE" in search.summary

    # project inspection path still available
    inspect_res = _run_command("INSPECT_WEBSITE_PROJECT", "inspect website project")
    assert bool(inspect_res.summary.strip())

    # tts verified status flag
    set_selected_verified_audio_backend("verified_local_pyttsx3")
    cap = _run_command("SHOW_CAPABILITY_HEALTH", "show capability health")
    assert "verified_local_pyttsx3" in cap.summary

    # runtime mismatch command
    mm = _run_command("SHOW_RUNTIME_CONFIG_MISMATCHES", "show runtime config mismatches")
    assert "Runtime config mismatches" in mm.summary

    print("SMOKE PASS phase602_runtime_truthfulness")


if __name__ == "__main__":
    main()

