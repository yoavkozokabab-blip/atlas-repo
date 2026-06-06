# Phase 182A — Operations Security Hardening

**Date:** 2026-06-07  
**Status:** PASS  
**Scope:** Operations layer only — analytics, crash registry, support bundle, admin API.  
No graph engine, planning engine, impact engine, repository memory, persistence, trust integrity, billing, or website changes.

---

## Findings Addressed

| ID | Finding | Status |
|----|---------|--------|
| P0-1 | `/api/analytics/event` accepted arbitrary payloads | **Closed** |
| P0-2 | Crash registry stored raw exception text with secrets / paths | **Closed** |
| P1-A | Support bundle included full analytics JSONL (with field values) | **Closed** |
| P1-B | Admin feedback endpoint returned raw payloads including email | **Closed** |
| P1-C | Admin crash summary exposed raw crash text | **Closed** |

---

## P0-1 — Analytics Sanitization

### Field whitelist

External events arriving via `POST /api/analytics/event` are stripped to the allowed field set before persistence. Unknown fields are silently dropped.

**Allowed user fields:**
`event`, `event_type`, `timestamp`, `duration_ms`, `token_count`, `file_count`, `repo_language`, `workflow_type`, `success`

**System-only fields** (added by the pipeline, not accepted from callers):
`installation_id`, `pipeline_version`, `channel`, `product`, `ts`, `at`, `version`, `crash_id`, `kind`, `exc_type`, and numeric export/scan counters.

Implementation: `sanitize_analytics_payload(event, properties, for_external=True/False)` in `operations.py`.

### Size limits

- Max field length: **256 characters** (strings truncated before content checks)
- Max event size: **4 096 bytes** — events exceeding this after sanitization are reduced to system fields only

### Content rejection

String field values are checked against `_SOURCE_CODE_RE` before storage. Rejected patterns:

| Pattern family | Examples caught |
|---|---|
| Python | `def foo(`, `class Bar:`, `import x`, `from x import y`, `if __name__ ==` |
| JavaScript | `function f(`, `const x =`, `let x =`, `var x =`, `=> {`, `console.log(`, `require("` |
| Prompt injection | `You are a …`, `As an AI`, `Human: `, `Assistant: `, `[INST]`, `<\|im_start\|>`, `ignore previous instructions` |
| Export content | `ATLAS_REPOSITORY_MEMORY`, `## Repository`, `# ==…` section dividers |
| Markdown fences | ` ``` ` |

Values matching any pattern are replaced with `[redacted-content]`.

### Secret rejection in field values

`_SECRET_RE` (compiled with `re.IGNORECASE`) redacts:

`sk-ant-…`, `sk-…{8+}`, `ghp_…`, `github_pat_…`, `ghs_…`, `xoxb-…`, `xoxp-…`, JWT three-part, `Bearer <token>`, `jwt=…`, `Authorization: …`, and generic `key=value` / `token=value` / `secret=value` patterns.

Values matching are replaced with `[redacted-secret]`.

---

## P0-2 — Crash Registry Redaction

### Before (old)
`record_crash()` stored `"message": raw_message[:2000]` containing unredacted tokens, paths, and exception text.

### After (new)

```
safe_message = _sanitize_crash_text(message)[:500]
```

`_sanitize_crash_text()` applies two passes:
1. `_SECRET_RE` — replaces all token patterns with `[redacted-secret]`
2. `_PATH_RE` — replaces absolute filesystem paths with `[path-redacted]`

**`_PATH_RE` catches:**
- Windows: `C:\Users\alice\...`
- Linux: `/home/alice/...`
- macOS: `/Users/alice/...`
- Other POSIX: `/tmp/…`, `/var/…`, `/private/…`, `/opt/…`

### Stored schema (new)

```json
{
  "crash_id": "a3f1c8...",
  "ts": 1749340800.0,
  "at": "2026-06-07T10:00:00Z",
  "kind": "scan_failure",
  "exc_type": "FileNotFoundError",
  "safe_summary": "Cannot read [path-redacted]",
  "version": "0.1.0-beta",
  "installation_id": "abc123..."
}
```

`context` dicts are no longer persisted — raw exception context is discarded at the boundary.

---

## P1 — Support Bundle Hardening

### Analytics JSONL stripping

`_strip_analytics_payloads(text)` in `install_support.py` is applied to `analytics.jsonl` before it is included in the support bundle ZIP. It retains only the envelope fields: `ts`, `event`, `at`, `version`, `kind`. All other fields (payload values, token counts, installation IDs) are dropped.

```python
# Before: {"ts":1.0,"event":"export_created","token_count":1200,"repo_language":"python","installation_id":"abc"}
# After:  {"ts":1.0,"event":"export_created"}
```

### Crash secret containment

Crash records stored via `record_crash()` already have secrets and paths removed at write time (P0-2). The support bundle passes all sections through `_sanitize_support_payload()` → `_redact_support_text()` as an additional layer.

### Persistence markers

`_redact_persistence_secret_markers()` continues to strip `persistence_secret` labels. Verified passing in 182A test suite.

---

## P1 — Admin Data Minimization

### Feedback inbox

`GET /api/operations/feedback` now returns `list_feedback_minimized()` instead of raw `list_feedback()`.

`_minimize_feedback_item()` projects:

| Kept | Dropped |
|------|---------|
| `feedback_id` | `email` |
| `category` | `diagnostics_summary` |
| `timestamp` | `build_commit` |
| `version` | raw `message` (full) |
| `page` | |
| `summary` (first 120 chars of message) | |

Email, diagnostics payloads, and build metadata are not exposed to the admin inbox endpoint.

### Crash summary

`crash_summary()` wraps each item through `_minimize_crash_item()` before returning `"recent"`:

| Kept | Dropped |
|------|---------|
| `crash_id` | raw `context` dict |
| `at` | full stack trace |
| `kind` | |
| `exc_type` | |
| `version` | |
| `message` (safe_summary, ≤ 160 chars) | |

### Beta insights dashboard

`beta_insights_dashboard()` aggregates from the minimized `feedback_inbox_summary()` and `crash_summary()`. No raw items propagate into the insights response.

---

## Files Changed

| File | Change |
|------|--------|
| `jarvis_desktop/operations.py` | Replaced `_SOURCE_CODE_RE` (fixed anchors, added prompt/export/JS patterns); replaced `_SECRET_RE` (fixed Python 3.13 inline-flag error, added `ghs_`, `xoxp-`, `secret=value`); replaced `_PATH_RE` (added macOS /Users, /private, /opt); `record_crash()` stores `safe_summary` not raw message, drops context; added `list_feedback_minimized()`; `_minimize_crash_item()` reads `safe_summary`; `feedback_inbox_summary()` uses minimized items |
| `jarvis_desktop/api.py` | `track_analytics_event()` applies `sanitize_analytics_payload(for_external=True)`; `operations_feedback_inbox()` returns `list_feedback_minimized()` |
| `jarvis_desktop/install_support.py` | `collect_error_logs()` applies `_strip_analytics_payloads()` to `analytics.jsonl` before bundling |
| `jarvis_desktop/tests/test_phase182_beta_operations.py` | Updated `test_feedback_inbox_lists_submissions` to check `"summary"` key (P1 minimization) |
| `jarvis_desktop/tests/test_phase182a_operations_security.py` | **New** — 34 tests |
| `reports/phase182a_operations_security.md` | This report |

---

## Test Results

```
py -3 -m pytest jarvis_desktop/tests/test_phase182_beta_operations.py
                 jarvis_desktop/tests/test_phase182a_operations_security.py -v

54 passed in 1.17s
```

### 182A test inventory

| Test | Covers |
|------|--------|
| `test_analytics_whitelist_strips_unknown_fields` | P0-1 whitelist |
| `test_analytics_whitelist_allows_all_spec_fields` | P0-1 whitelist |
| `test_analytics_rejects_python_code` | P0-1 source-code rejection |
| `test_analytics_rejects_javascript_code` | P0-1 source-code rejection |
| `test_analytics_rejects_prompt_injection` | P0-1 prompt rejection |
| `test_analytics_rejects_export_content` | P0-1 export-content rejection |
| `test_analytics_rejects_json_with_secrets` | P0-1 secret rejection |
| `test_analytics_max_field_length` | P0-1 256-char limit |
| `test_analytics_size_limit` | P0-1 4 KB limit |
| `test_analytics_endpoint_strips_oversized_payload` | P0-1 API boundary |
| `test_crash_log_redacts_tokens` | P0-2 token redaction |
| `test_crash_log_redacts_api_key_kv` | P0-2 key=value redaction |
| `test_crash_log_redacts_bearer_header` | P0-2 Bearer redaction |
| `test_crash_log_redacts_jwt` | P0-2 JWT redaction |
| `test_crash_log_redacts_paths_windows` | P0-2 Windows path |
| `test_crash_log_redacts_paths_linux` | P0-2 Linux path |
| `test_crash_log_redacts_paths_macos` | P0-2 macOS path |
| `test_crash_record_stores_only_safe_fields` | P0-2 schema |
| `test_support_bundle_no_analytics_payload_leak` | P1 bundle |
| `test_strip_analytics_payloads_keeps_only_envelope` | P1 bundle |
| `test_support_bundle_no_crash_secret_leakage` | P1 bundle |
| `test_support_bundle_no_persistence_markers` | P1 bundle |
| `test_admin_feedback_no_raw_payload` | P1 admin minimization |
| `test_admin_feedback_summary_no_raw_items_in_insights` | P1 admin minimization |
| `test_admin_crashes_no_raw_messages` | P1 admin minimization |
| `test_admin_insights_crashes_minimized` | P1 admin minimization |
| `test_internal_pipeline_rejects_source_code_in_message` | P0-1 internal |
| `test_internal_pipeline_allows_numeric_fields` | P0-1 safe passthrough |
| `test_sanitize_crash_text_removes_sk_key` | P0-2 unit |
| `test_sanitize_crash_text_removes_github_pat` | P0-2 unit |
| `test_sanitize_crash_text_removes_windows_path` | P0-2 unit |
| `test_sanitize_crash_text_removes_linux_path` | P0-2 unit |
| `test_sanitize_crash_text_removes_macos_path` | P0-2 unit |
| `test_sanitize_crash_text_preserves_safe_content` | P0-2 no false-positive |

---

## Privacy Review

| Surface | Before 182A | After 182A |
|---------|-------------|------------|
| Analytics JSONL | Arbitrary key-value pairs from API callers | Whitelisted fields only; source code, prompts, secrets rejected |
| Crash registry | Raw exception text, absolute paths, context dicts | `safe_summary` only (redacted); no context dict; no raw path |
| Support bundle (analytics) | Full analytics rows with all fields | Envelope only: `ts`, `event`, `at` |
| Support bundle (crashes) | Passed through `_sanitize_support_payload` | P0-2 redaction at write time + `_sanitize_support_payload` |
| Admin feedback inbox | Raw feedback rows including email | Minimized: `summary`(120 chars), `category`, `page`, `feedback_id`, `timestamp` |
| Admin crash list | Raw crash rows with context dicts | Minimized: `kind`, `exc_type`, `safe_summary`(160 chars), `at`, `version` |

---

## Known Limitations

1. **Repo name in crash messages**: Repo names embedded in prose (not paths) are not redacted — only path components are caught. A message like `Failed while analyzing my-secret-project` would survive. Path-based repo references (e.g. `/home/user/my-secret-project`) are redacted.

2. **`_SOURCE_CODE_RE` false positives**: `const x =` and `let x =` could fire on unusual event values in non-code contexts. The practical risk for the analytics use case is very low (these fields are expected to hold short categorical strings).

3. **Analytics JSONL in support bundle**: After stripping, only `ts/event/at` survive. This means the support bundle cannot be used to diagnose analytics pipeline issues in field, but that trade-off is intentional (privacy > debuggability for the bundle).

4. **Admin endpoint secret**: `ATLAS_ADMIN=1` is a simple environment variable gate. For production multi-user deployments a proper role-based check would be needed.

---

## Systems Not Modified

- Graph engine  
- Planning engine  
- Impact engine  
- Repository memory  
- Persistence (Phase 181B)  
- Trust integrity  
- Billing  
- Website marketing
