"""Alpha first-run setup checklist (Phase 68)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ACTION_REQUIRED = "ACTION REQUIRED"


@dataclass
class SetupCheck:
    name: str
    status: CheckStatus
    detail: str


def _check_voice() -> SetupCheck:
    try:
        from voice.microphone import check_microphone_available

        check_microphone_available()
        from reliability.voice_health import show_voice_health

        body = show_voice_health()
        if "error" in body.lower() and "unavailable" in body.lower():
            return SetupCheck("voice", CheckStatus.ACTION_REQUIRED, body[:120])
        return SetupCheck("voice", CheckStatus.PASS, "Microphone and voice health OK")
    except Exception as exc:
        return SetupCheck("voice", CheckStatus.FAIL, str(exc)[:160])


def _check_tts() -> SetupCheck:
    try:
        from voice.pyttsx3_completion import run_direct_tts_isolated_test

        result = run_direct_tts_isolated_test("Alpha setup TTS check.")
        if result.ok:
            return SetupCheck("tts", CheckStatus.PASS, "Direct TTS path OK")
        return SetupCheck("tts", CheckStatus.ACTION_REQUIRED, result.error or "TTS returned false")
    except Exception as exc:
        return SetupCheck("tts", CheckStatus.FAIL, str(exc)[:160])


def _check_browser() -> SetupCheck:
    try:
        from browser.runtime import get_browser_runtime_state, test_real_browser

        ok, body = test_real_browser()
        st = get_browser_runtime_state()
        if ok and st.provider == "playwright":
            return SetupCheck("browser", CheckStatus.PASS, "Playwright browser OK")
        return SetupCheck("browser", CheckStatus.ACTION_REQUIRED, body[:120] or "browser not ready")
    except Exception as exc:
        return SetupCheck("browser", CheckStatus.FAIL, str(exc)[:160])


def _check_desktop_screenshot() -> SetupCheck:
    try:
        import config

        if not config.SCREEN_UNDERSTANDING_ENABLED:
            return SetupCheck(
                "desktop_screenshot",
                CheckStatus.ACTION_REQUIRED,
                "Set SCREEN_UNDERSTANDING_ENABLED=true",
            )
        from desktop.vision_runtime import capture_active_monitor

        ok, path, msg = capture_active_monitor()
        if ok and path and Path(path).is_file():
            return SetupCheck("desktop_screenshot", CheckStatus.PASS, f"Captured {path}")
        return SetupCheck("desktop_screenshot", CheckStatus.ACTION_REQUIRED, msg[:120])
    except Exception as exc:
        return SetupCheck("desktop_screenshot", CheckStatus.FAIL, str(exc)[:160])


def _check_memory() -> SetupCheck:
    try:
        import config

        if not config.MEMORY_ENABLED:
            return SetupCheck("memory_store", CheckStatus.ACTION_REQUIRED, "MEMORY_ENABLED=false")
        from memory.store import get_personal_memory

        store = get_personal_memory()
        entry = store.remember("alpha setup probe", category="session", tags=["alpha_setup"])
        if entry.entry_id:
            store.forget("alpha setup probe")
            return SetupCheck("memory_store", CheckStatus.PASS, "Read/write OK")
        return SetupCheck("memory_store", CheckStatus.FAIL, "remember returned no id")
    except Exception as exc:
        return SetupCheck("memory_store", CheckStatus.FAIL, str(exc)[:160])


def _check_integrations() -> SetupCheck:
    try:
        import config

        email = getattr(config, "INTEGRATIONS_EMAIL_MODE", "mock")
        cal = getattr(config, "INTEGRATIONS_CALENDAR_MODE", "mock")
        from reliability.integrations_health import summarize_my_inbox

        body = summarize_my_inbox(5)
        if "MOCK MODE" in body and email == "mock":
            return SetupCheck(
                "integrations_mode",
                CheckStatus.PASS,
                f"mock mode (email={email}, calendar={cal})",
            )
        if "REAL READONLY" in body:
            return SetupCheck(
                "integrations_mode",
                CheckStatus.PASS,
                f"readonly mode (email={email}, calendar={cal})",
            )
        return SetupCheck("integrations_mode", CheckStatus.ACTION_REQUIRED, body[:100])
    except Exception as exc:
        return SetupCheck("integrations_mode", CheckStatus.FAIL, str(exc)[:160])


def _check_permissions() -> SetupCheck:
    issues: list[str] = []
    try:
        from voice.microphone import check_microphone_available

        check_microphone_available()
    except Exception as exc:
        issues.append(f"mic:{exc}")
    import config

    if not config.SCREEN_UNDERSTANDING_ENABLED:
        issues.append("screen_understanding_disabled")
    if config.COMPUTER_CONTROL_ENABLED and not getattr(config, "DEVELOPER_MODE", False):
        issues.append("computer_control_enabled_in_alpha")
    if issues:
        return SetupCheck("permissions", CheckStatus.ACTION_REQUIRED, "; ".join(issues)[:160])
    return SetupCheck("permissions", CheckStatus.PASS, "Mic and screen permissions OK for alpha")


def _check_logs_folder() -> SetupCheck:
    import config

    paths = [
        config.DATA_DIR,
        getattr(config, "ALPHA_SESSIONS_DIR", config.DATA_DIR / "alpha_sessions"),
        config.PROJECT_ROOT / "reports",
    ]
    for path in paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test = path / ".alpha_write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
        except OSError as exc:
            return SetupCheck("logs_folder", CheckStatus.FAIL, f"{path}: {exc}")
    return SetupCheck("logs_folder", CheckStatus.PASS, "data/ and reports/ writable")


def run_alpha_setup_checks() -> list[SetupCheck]:
    return [
        _check_voice(),
        _check_tts(),
        _check_browser(),
        _check_desktop_screenshot(),
        _check_memory(),
        _check_integrations(),
        _check_permissions(),
        _check_logs_folder(),
    ]


def format_alpha_setup_report(checks: list[SetupCheck] | None = None) -> str:
    checks = checks or run_alpha_setup_checks()
    lines = ["Alpha setup check", ""]
    for chk in checks:
        lines.append(f"  [{chk.status.value}] {chk.name}: {chk.detail}")
    passed = sum(1 for c in checks if c.status == CheckStatus.PASS)
    lines.append("")
    lines.append(f"Summary: {passed}/{len(checks)} PASS")
    return "\n".join(lines)
