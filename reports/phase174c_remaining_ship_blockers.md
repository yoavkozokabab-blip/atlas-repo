# Phase 174C Remaining Ship Blockers

Date: 2026-06-06
Verdict: NO-GO until the blockers below are resolved.

## Blocker Table

| ID | Severity | Attack | Root cause | Risk |
| --- | --- | --- | --- | --- |
| 174C-SB1 | P0 | A7 unsupported repo shallow graph | Graph health says `healthy` when only an incidental Python helper is represented. Weak-graph gate only checks `unsupported_language_limited`. | Atlas can produce plausible but wrong Build/Investigation output on unsupported repos. |
| 174C-SB2 | P0 | A10 support bundle redaction | Redaction handles paths and `SECRET_*` but misses `api_key=...` style secrets. | Support bundles can leak user credentials or secrets. |
| 174C-SB3 | P1 | A9 export replay | Old memory packet has `scan_id` but no signature/staleness/replay warning. | Old copied context can look valid in external LLM chats after repo changes. |

## 174C-SB1: Unsupported Repo False Success

Reproduction:

1. Create a Go-style repo with `cmd/server/main.go`, `pkg/events/bus.go`, and incidental `hack/boilerplate.py`.
2. Run `api.scan_repository(repo)`.
3. Run `api.plan_change("add event bus tracing")`.
4. Run `api.investigate_symptom("why are duplicate events being fired")`.

Actual:

- Scan: `module_count=1`, `dependency_edges=0`, graph health label `healthy`.
- Build: `ok=true`, `confidence=low-medium`, recommends `hack/boilerplate.py`.
- Investigation: `ok=true`, `confidence=low-medium`, likely area `hack/boilerplate.py`.
- Impact: correctly refuses `pkg/events/bus.go` as `target_not_resolved`.

Root cause:

The weak-graph gate only blocks `unsupported_language_limited`. The scanner classifies this shallow unsupported repo as healthy because the single Python helper has no unresolved imports.

Risk:

A beta user scanning Kubernetes/Go/Java/C# style repos can receive apparently grounded output for unrelated helper files. This directly damages trust.

Suggested mitigation:

Make graph health account for language support and coverage: unsupported production files, represented modules versus total code files, and incidental helper dominance. Gate Build/Investigation when graph evidence is too shallow, unless the user provides exact file/symbol evidence.

## 174C-SB2: Support Bundle Secret Leak

Reproduction:

1. Write launcher log line: `Failure at <absolute path> with SECRET_PHASE174C_LOG and api_key=LEAK_ME`.
2. Run `api.export_support_bundle()`.
3. Decode the bundle and inspect `logs/launcher.log`.

Actual:

```text
Failure at [path-redacted] with [secret-redacted] and api_key=LEAK_ME
```

Root cause:

`install_support._redact_support_text()` only redacts absolute paths and `SECRET_[A-Z0-9_]+`. It does not redact common key/value secret patterns.

Risk:

A support bundle can leak API keys, tokens, passwords, or authorization values from logs.

Suggested mitigation:

Add generic key/value redaction for `api_key`, `token`, `secret`, `password`, `authorization`, `bearer`, and common cloud credential fields. Test redaction across plain logs and JSON diagnostics.

## 174C-SB3: Old Memory Packet Replay Metadata

Reproduction:

1. Scan repo A.
2. Copy `api.session_export_packet()` output.
3. Select repo B.
4. Request a new session export.

Actual:

- New export is blocked with `requires_rescan`.
- Old packet includes `scan_id`.
- Old packet lacks scan signature, stale warning, replay warning, or rescan caveat.

Root cause:

`ATLAS_REPOSITORY_MEMORY v1` is compact, but it is not self-invalidating when copied outside Atlas.

Risk:

External LLM chats can continue using stale memory packets. Atlas correctly blocks new exports, but cannot protect already-copied text unless the packet itself carries a validity boundary.

Suggested mitigation:

Add a compact warning and signature prefix to memory packet text, for example: `valid_for_scan=<scan_id> sig=<prefix>; if repo changed or Atlas says refresh/rescan, discard this packet`.

## Non-Blocker Observations

- Edited scanned files were blocked from export with `stale_outside_plan` rather than literal `stale_scan`; this is acceptable because exports are refused and the targeted-refresh path explains the state.
- Git HEAD changes were blocked with `stale_git_head_changed` in the synthetic `.git` test.
- Late-file changes beyond 2500 files were detected and blocked.
- Tampered memory JSON did not appear in exports.
- Forced memory write failure was visible as `memory_persistence_status=failed` and did not claim persistent memory.
- Concurrent scan/select/export probes did not leak wrong-repo memory.

## Release Recommendation

NO-GO for 20 supervised beta users.

The stale-context P0 class is mostly closed, but unsupported-repo false success and support-bundle secret leakage are enough to block beta expansion.
