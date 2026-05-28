"""Smoke test: process env must win over .env for critical realtime flags (Phase 58.1)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_probe(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    code = """
import sys
from pathlib import Path
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import config
from core.env_precedence import collect_realtime_precedence_warnings, get_env_resolution
from voice.runtime_mode import format_stable_mode_banner, is_realtime_experimental_mode

assert config.VOICE_RUNTIME_MODE == "realtime_experimental", config.VOICE_RUNTIME_MODE
assert config.VOICE_RUNTIME_STABLE is False, config.VOICE_RUNTIME_STABLE
assert config.REALTIME_TTS_ENABLED is True, config.REALTIME_TTS_ENABLED
assert config.TTS_SAFE_MODE is False, config.TTS_SAFE_MODE
assert config.ELEVENLABS_WEBSOCKET_ENABLED is True, config.ELEVENLABS_WEBSOCKET_ENABLED
assert is_realtime_experimental_mode()

mode_raw, mode_source = get_env_resolution("VOICE_RUNTIME_MODE")
assert mode_source == "process_env", mode_source
assert mode_raw == "realtime_experimental", mode_raw

safe_raw, safe_source = get_env_resolution("TTS_SAFE_MODE")
assert safe_source == "process_env", safe_source
assert safe_raw.lower() in {"false", "0", "no"}, safe_raw

assert not collect_realtime_precedence_warnings(), collect_realtime_precedence_warnings()

banner = format_stable_mode_banner()
assert "REALTIME EXPERIMENTAL" in banner, banner
print("ENV_PRECEDENCE_PROBE_OK")
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> None:
    env = os.environ.copy()
    env["VOICE_RUNTIME_MODE"] = "realtime_experimental"
    env["TTS_SAFE_MODE"] = "false"
    env["ELEVENLABS_WEBSOCKET_ENABLED"] = "true"
    env["REALTIME_TTS_ENABLED"] = "true"
    env["REALTIME_FULL_DUPLEX_ENABLED"] = "true"

    probe = _run_probe(env)
    if probe.returncode != 0:
        print(probe.stdout)
        print(probe.stderr, file=sys.stderr)
        raise SystemExit(probe.returncode)
    assert "ENV_PRECEDENCE_PROBE_OK" in probe.stdout
    print("OK process env overrides .env for critical realtime flags")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    registry = ActionRegistry()
    action = registry._actions.get(Intent.SHOW_RUNTIME_CONFIG_SOURCES.value)
    assert action is not None, "show runtime config sources action missing"
    result = action.execute(
        CommandRequest(raw_text="show runtime config sources", intent=Intent.SHOW_RUNTIME_CONFIG_SOURCES)
    )
    assert "Runtime config sources" in result.summary
    assert "VOICE_RUNTIME_MODE" in result.summary
    print("OK show runtime config sources command")

    print("SMOKE PASS env_precedence")


if __name__ == "__main__":
    main()
