"""Phase 65 Track C — browser reliability."""

from __future__ import annotations

from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


def show_browser_health() -> str:
    from browser.runtime import get_browser_runtime_state

    st = get_browser_runtime_state()
    lines = [
        "Browser health (Phase 65):",
        f"  provider: {st.provider}",
        f"  session_active: {st.session_active}",
        f"  browser_process_alive: {st.browser_process_alive}",
        f"  browser_visible: {st.browser_visible}",
        f"  last_action_success: {st.last_action_success}",
        f"  last_exception: {st.last_exception or 'none'}",
        f"  current_url: {st.current_url or 'n/a'}",
        f"  tab_count: {st.tab_count}",
    ]
    return "\n".join(lines)


def run_browser_acceptance() -> TrackScore:
    score = TrackScore(track="Browser", current_pct=0.0, target_pct=85.0)

    def _state_readable() -> tuple[bool, str]:
        from browser.runtime import get_browser_runtime_state

        st = get_browser_runtime_state()
        return True, f"provider={st.provider}"

    def _open_browser() -> tuple[bool, str]:
        from browser.runtime import get_browser_runtime_state, open_browser

        body = open_browser("about:blank")
        st = get_browser_runtime_state()
        if st.provider == "mock":
            return True, "mock mode"
        return st.last_action_success or "BROWSER" in body, body[:120]

    def _nav_recovery() -> tuple[bool, str]:
        from browser.runtime import recover_navigation

        return recover_navigation("https://example.com")

    def _crash_recovery() -> tuple[bool, str]:
        from browser.runtime import recover_browser_session

        ok, msg = recover_browser_session()
        return ok, msg[:120]

    def _summarize() -> tuple[bool, str]:
        from browser.runtime import summarize_current_page

        body = summarize_current_page()
        return bool(body), body[:120]

    def _active_page() -> tuple[bool, str]:
        from browser.runtime import active_tab_status

        body = active_tab_status()
        return "tab" in body.lower() or "active" in body.lower(), body[:120]

    score.cases.extend(
        [
            run_case("runtime_state", _state_readable),
            run_case("open_browser", _open_browser),
            run_case("navigation_recovery", _nav_recovery),
            run_case("crash_recovery", _crash_recovery),
            run_case("summarize_page", _summarize),
            run_case("active_page_status", _active_page),
        ]
    )
    score.finalize_score()
    if score.pass_rate < 95:
        score.blockers.append("Browser acceptance below 95% target.")
        score.recommendations.append("Install Playwright browsers and verify visible launch with test real browser.")
    write_report(reports_dir() / "browser_reliability_report.md", format_track_report(score).splitlines())
    return score
