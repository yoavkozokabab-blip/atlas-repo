# Atlas v1.0.5 — Product Funnel Validation (local/sandbox)

Date: 2026-07-18. All validation is local/sandbox; no production conversions
are claimed or fabricated.

## Funnel events and where they are validated

| Funnel event | Emitter | Validated by |
| --- | --- | --- |
| website_session_started | website AnalyticsClient (pseudonymous ids, dedup) | `qa/analytics-auth.spec.ts` (16/16) — contract, origin gating, schema |
| download_clicked | website `data-evt="download_click"` on Download CTAs | full-site QA confirms CTA present on nav + hero + /download |
| app_first_opened | desktop `record_first_run` (exactly once per install) | `test_remote_analytics.py` + code path gates on `analytics-first-run.json` |
| demo_started | desktop `demo_loaded` | `test_v105_analytics_optout.py` emit-path checks |
| repository_selected | desktop `select_repository` flow | usage/persistence suites |
| scan_completed | desktop `scan_completed` (cache-hit + miss) | scan suites; emitted with count buckets only |
| first_ask_completed | desktop `copilot_question` | Ask suites |
| first_impact_completed | desktop `impact_analyzed` | Impact suites |
| agent_connected | desktop `mcp_connect` (tool + outcome only) | MCP suites |
| returning_app_session | desktop `app_started` on subsequent launches | operations pipeline tests |

## Privacy envelope (enforced, not aspirational)

- Desktop remote analytics: allowlisted event names + allowlisted properties,
  numeric clamping, sensitive-pattern scrub, pseudonymous installation id
  format-checked (`analytics_remote._safe_properties`).
- Never emitted: repository names, paths, filenames, code, prompts, answers,
  evidence text, symbol names, MCP payloads, command lines, tokens, emails.
  Regression-guarded by `test_remote_analytics.py` (private-path payloads are
  stripped) and `test_phase116f_analytics_isolation_hardening.py`.
- Opt-out is authoritative at the lowest emitter and covers the accounts
  telemetry mirror; the offline queue is bounded (100 events / 256 KB) and
  deleted on opt-out.

## Key product metrics (definitions locked for v1.0.5)

- **Activation**: first successful Ask or Impact (`first_ask_completed` /
  `first_impact_completed`).
- **Aha moment**: Impact completes with ≥1 evidence-backed affected file
  (coarse result field on `impact_analyzed`).
- **Agent activation**: `mcp_connect` with `ok=true` following a real
  handshake (Configured ≠ Connected is preserved in the UI).
- **Return**: `app_started` with a prior successful workflow recorded locally.

## Sandbox validation performed

- Website: 21 routes × 2 viewports loaded against a production build with the
  analytics endpoint active; events accepted (202), hostile origins rejected
  (403), over-rate traffic rejected (429 + Retry-After) and the client backs
  off. Zero console errors after backoff behavior.
- Desktop: enabled → events written locally and queued remotely (bounded);
  disabled → zero emission on every path. Verified by 45 analytics tests.
