"""Strict grading helpers (Phase 66.1)."""

from __future__ import annotations

from pathlib import Path

import config
from validation.strict_framework import ProviderKind, ScenarioStatus, StrictScenarioOutcome


def _out(
    status: ScenarioStatus,
    provider: ProviderKind,
    *,
    user_visible: bool = False,
    external_action_performed: bool = False,
    evidence_path: str = "",
    error_message: str = "",
    detail: str = "",
    recovered: bool = False,
) -> StrictScenarioOutcome:
    return StrictScenarioOutcome(
        status=status,
        provider=provider,
        user_visible=user_visible,
        external_action_performed=external_action_performed,
        evidence_path=evidence_path,
        error_message=error_message,
        detail=detail,
        recovered=recovered,
    )


def grade_browser_after_action(body: str, *, require_url: bool = True) -> StrictScenarioOutcome:
    from browser.runtime import get_browser_runtime_state

    st = get_browser_runtime_state()
    detail = body[:200]
    if "MOCK MODE" in body or st.provider != "playwright":
        if st.last_action_success or "mock" in body.lower():
            return _out(
                ScenarioStatus.MOCK_PASS,
                ProviderKind.MOCK,
                detail=detail,
                error_message="mock_fallback",
            )
        return _out(ScenarioStatus.FAIL, ProviderKind.MOCK, error_message=st.last_exception or "mock_failed", detail=detail)
    if not st.browser_process_alive:
        return _out(
            ScenarioStatus.FAIL,
            ProviderKind.REAL,
            error_message="browser_process_not_alive",
            detail=detail,
        )
    if not st.last_action_success:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.REAL,
            error_message=st.last_exception or "last_action_failed",
            detail=detail,
        )
    evidence = st.last_screenshot_path or ""
    dom_ok = bool((st.last_dom_excerpt or "").strip())
    url_ok = bool((st.current_url or "").strip())
    title_ok = bool((st.active_tab_title or "").strip())
    if require_url and (not url_ok or not title_ok):
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.REAL,
            error_message="missing_url_or_title",
            detail=f"url={st.current_url} title={st.active_tab_title}",
            evidence_path=evidence,
        )
    if not evidence and not dom_ok:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.REAL,
            error_message="missing_dom_or_screenshot_evidence",
            detail=detail,
            user_visible=st.browser_visible,
        )
    return _out(
        ScenarioStatus.REAL_PASS,
        ProviderKind.REAL,
        user_visible=st.browser_visible,
        external_action_performed=True,
        evidence_path=evidence,
        detail=f"mode={'visible' if st.browser_visible else 'headless'} url={st.current_url}",
    )


def grade_desktop_capture(ok: bool, path: str, msg: str) -> StrictScenarioOutcome:
    if not config.SCREEN_UNDERSTANDING_ENABLED:
        return _out(ScenarioStatus.FAIL, ProviderKind.UNAVAILABLE, error_message="screen_understanding_disabled", detail=msg)
    if "SIMULATED" in msg or "disabled" in msg.lower():
        return _out(ScenarioStatus.MOCK_PASS, ProviderKind.MOCK, error_message="simulated_or_disabled", detail=msg)
    if not ok or not path or not Path(path).is_file():
        return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="capture_failed", detail=msg)
    return _out(
        ScenarioStatus.REAL_PASS,
        ProviderKind.REAL,
        external_action_performed=True,
        evidence_path=path,
        detail=msg[:120],
    )


def grade_desktop_ocr(
    text: str,
    engine: str,
    *,
    screenshot_path: str = "",
) -> StrictScenarioOutcome:
    if not config.SCREEN_UNDERSTANDING_ENABLED:
        return _out(ScenarioStatus.FAIL, ProviderKind.UNAVAILABLE, error_message="screen_understanding_disabled")
    if engine in ("disabled", "skipped", "none", "error"):
        return _out(ScenarioStatus.MOCK_PASS, ProviderKind.MOCK, error_message=f"ocr_{engine}", detail=f"len={len(text)}")
    if engine == "blocked":
        return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.DEGRADED, error_message="ocr_blocked_sensitive_window")
    has_shot = bool(screenshot_path and Path(screenshot_path).is_file())
    if not text.strip():
        if has_shot:
            return _out(
                ScenarioStatus.DEGRADED_PASS,
                ProviderKind.REAL,
                error_message="empty_ocr_text",
                evidence_path=screenshot_path,
                detail=f"engine={engine} screenshot=yes",
            )
        return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="empty_ocr_no_screenshot")
    evidence = screenshot_path if has_shot else "ocr:text"
    return _out(
        ScenarioStatus.REAL_PASS,
        ProviderKind.REAL,
        evidence_path=evidence,
        detail=f"engine={engine} chars={len(text)}",
    )


def grade_desktop_control(body: str, *, typed: bool = False) -> StrictScenarioOutcome:
    if not config.COMPUTER_CONTROL_ENABLED:
        return _out(
            ScenarioStatus.FAIL,
            ProviderKind.UNAVAILABLE,
            error_message="COMPUTER_CONTROL_ENABLED=false",
            detail=body[:120],
        )
    if "Approval required" in body:
        return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.REAL, error_message="approval_gate", detail=body[:120])
    if "disabled" in body.lower() or "SIMULATED" in body:
        return _out(ScenarioStatus.MOCK_PASS, ProviderKind.MOCK, error_message="simulated_control", detail=body[:120])
    if typed and "Typed" in body:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, external_action_performed=True, detail=body[:120])
    if "Focused" in body or "Moved" in body or "Clicked" in body:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, external_action_performed=True, detail=body[:120])
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="control_action_failed", detail=body[:120])


def grade_voice_simulated_routing(ok: bool, detail: str) -> StrictScenarioOutcome:
    """Intent/routing-only checks — never real voice success."""
    if ok:
        return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.DEGRADED, detail=detail, error_message="simulated_routing_only")
    return _out(ScenarioStatus.FAIL, ProviderKind.DEGRADED, error_message="routing_failed", detail=detail)


def grade_voice_runtime_probe(
    ok: bool,
    detail: str,
    *,
    exercised_audio: bool = False,
    recovered: bool = False,
) -> StrictScenarioOutcome:
    if exercised_audio and ok:
        return _out(
            ScenarioStatus.REAL_PASS,
            ProviderKind.REAL,
            external_action_performed=True,
            detail=detail,
            recovered=recovered,
        )
    if ok:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.DEGRADED,
            detail=detail,
            error_message="config_probe_only",
            recovered=recovered,
        )
    return _out(
        ScenarioStatus.FAIL,
        ProviderKind.UNAVAILABLE,
        error_message="voice_probe_failed",
        detail=detail,
        recovered=recovered,
    )


def grade_memory_recall(ok: bool, detail: str) -> StrictScenarioOutcome:
    if not config.MEMORY_ENABLED:
        return _out(ScenarioStatus.FAIL, ProviderKind.UNAVAILABLE, error_message="MEMORY_ENABLED=false", detail=detail)
    if ok:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, detail=detail)
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="recall_miss", detail=detail)


def grade_memory_write(ok: bool, entry_id: str) -> StrictScenarioOutcome:
    if not config.MEMORY_ENABLED:
        return _out(ScenarioStatus.FAIL, ProviderKind.UNAVAILABLE, error_message="MEMORY_ENABLED=false")
    if ok and entry_id:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, detail=entry_id)
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="remember_failed")


def grade_coding_filesystem(ok: bool, detail: str) -> StrictScenarioOutcome:
    if ok:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, detail=detail[:120])
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="coding_task_failed", detail=detail[:120])


def grade_integration_mock(ok: bool, body: str) -> StrictScenarioOutcome:
    """Mock provider — never real_pass."""
    if "REAL READONLY" in body:
        return _out(ScenarioStatus.FAIL, ProviderKind.MOCK, error_message="expected_mock_banner", detail=body[:120])
    if "MOCK MODE" not in body:
        return _out(ScenarioStatus.FAIL, ProviderKind.MOCK, error_message="missing_mock_banner", detail=body[:120])
    if ok:
        return _out(ScenarioStatus.MOCK_PASS, ProviderKind.MOCK, detail=body[:120])
    return _out(ScenarioStatus.FAIL, ProviderKind.MOCK, error_message="integration_failed", detail=body[:120])


def grade_integration_readonly(ok: bool, body: str) -> StrictScenarioOutcome:
    """Read-only real provider — real_pass when REAL READONLY banner present."""
    if "REAL READONLY" not in body:
        if "MOCK MODE" in body:
            return grade_integration_mock(ok, body)
        return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="missing_readonly_banner", detail=body[:120])
    if ok:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, external_action_performed=True, detail=body[:120])
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="readonly_integration_failed", detail=body[:120])


def grade_voice_real_conversation(body: str) -> StrictScenarioOutcome:
    """real_pass only when mic + STT + route + TTS all succeeded."""
    if "REAL VOICE CONVERSATION" not in body:
        return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="missing_real_voice_banner", detail=body[:120])
    mic = "mic_capture=yes" in body
    stt = "stt=yes" in body
    route = "route=yes" in body
    tts = "tts=yes" in body
    import re

    ev_m = re.search(r"evidence_path:\s*(\S+)", body)
    evidence = ev_m.group(1) if ev_m else ""
    if mic and stt and route and tts and evidence:
        return _out(
            ScenarioStatus.REAL_PASS,
            ProviderKind.REAL,
            external_action_performed=True,
            evidence_path=evidence,
            detail=body[:160],
        )
    if mic and tts:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.DEGRADED,
            error_message="partial_voice_pipeline",
            detail=body[:160],
            evidence_path=evidence,
        )
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="voice_pipeline_incomplete", detail=body[:120])


def grade_recovery_capability(
    ok: bool,
    restored: bool,
    capability: str,
    detail: str,
    *,
    evidence_path: str = "",
    before_ok: bool = False,
) -> StrictScenarioOutcome:
    """Recovery is real only when a failed capability is restored."""
    if ok and restored and (not before_ok or evidence_path):
        return _out(
            ScenarioStatus.REAL_PASS,
            ProviderKind.REAL,
            recovered=True,
            external_action_performed=True,
            evidence_path=evidence_path,
            detail=f"{capability}: {detail[:100]}",
        )
    if ok and restored:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.DEGRADED,
            recovered=True,
            error_message="recovery_without_prior_failure",
            detail=f"{capability}: {detail[:100]}",
        )
    if ok:
        return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.DEGRADED, error_message="recovery_partial", detail=detail[:120])
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message=f"{capability}_recovery_failed", detail=detail[:120])


def grade_recovery_browser(ok: bool, msg: str, recovered: bool) -> StrictScenarioOutcome:
    from browser.runtime import get_browser_runtime_state

    st = get_browser_runtime_state()
    if st.provider != "playwright":
        return _out(ScenarioStatus.MOCK_PASS, ProviderKind.MOCK, recovered=recovered, detail=msg, error_message="mock_recovery")
    if ok and recovered:
        return _out(ScenarioStatus.REAL_PASS, ProviderKind.REAL, recovered=True, external_action_performed=True, detail=msg)
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="recovery_failed", detail=msg)


def combine_multistep(
    step_outcomes: list[StrictScenarioOutcome],
    *,
    min_real_steps: int = 3,
) -> StrictScenarioOutcome:
    real_steps = [s for s in step_outcomes if s.status == ScenarioStatus.REAL_PASS]
    mock_used = any(s.status == ScenarioStatus.MOCK_PASS for s in step_outcomes)
    if any(s.status == ScenarioStatus.CRASH for s in step_outcomes):
        return _out(ScenarioStatus.CRASH, ProviderKind.UNAVAILABLE, error_message="step_crash", detail=f"steps={len(step_outcomes)}")
    if mock_used:
        return _out(
            ScenarioStatus.MOCK_PASS,
            ProviderKind.MOCK,
            error_message="mock_required_for_success",
            detail=f"real_steps={len(real_steps)}",
        )
    if len(real_steps) >= min_real_steps:
        evidence = next((s.evidence_path for s in real_steps if s.evidence_path), "")
        return _out(
            ScenarioStatus.REAL_PASS,
            ProviderKind.REAL,
            external_action_performed=True,
            evidence_path=evidence,
            detail=f"real_steps={len(real_steps)}",
        )
    if len(real_steps) >= 2:
        return _out(
            ScenarioStatus.DEGRADED_PASS,
            ProviderKind.DEGRADED,
            error_message="insufficient_real_steps",
            detail=f"real={len(real_steps)} need={min_real_steps}",
        )
    if any(s.status == ScenarioStatus.DEGRADED_PASS for s in step_outcomes):
        return _out(ScenarioStatus.DEGRADED_PASS, ProviderKind.DEGRADED, error_message="insufficient_real_steps", detail=f"real={len(real_steps)}")
    return _out(ScenarioStatus.FAIL, ProviderKind.REAL, error_message="multistep_failed", detail=f"real={len(real_steps)}")
