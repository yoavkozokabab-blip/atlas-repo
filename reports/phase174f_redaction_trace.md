# Phase 174F — Support Bundle Redaction Trace (A10)

**Date:** 2026-06-05  
**Attack:** 174E A10 — launcher.log canaries in support bundle  
**174E leaked string:** `Authorization: [REDACTED] BEARER_LEAK_ME`

## Attack input (launcher.log)

```
Failure at C:\...\abs SECRET_X api_key=LEAK_ME token=LEAK Authorization: Bearer X BEARER_LEAK_ME
```

## Generation path

```
POST /api/system/support-bundle
  server.dispatch → install_support.build_support_bundle()
    collect_error_logs()
      reads data_dir()/launcher.log (raw)
    logs = {name: _redact_support_text(text) for name, text in ...}
    zip: logs/launcher.log ← redacted copy
    diagnostics.json ← _sanitize_support_payload(beta_diagnostics)
      includes trust_integrity from trust_integrity_diagnostics()
```

## Redaction pipeline (`install_support.py`)

```
_redact_support_text(text)
  1. Windows absolute paths → [path-redacted]
  2. Unix /home|Users|var paths → [path-redacted]
  3. SECRET_[A-Z0-9_]+ → [secret-redacted]
  4. _redact_secret_values(out)
```

## Where the leak survived (pre-174F)

**Step 4 — Authorization header regex (partial match):**

```python
# OLD: consumed only first token after colon
re.sub(r"(?i)\bAuthorization:\s*[^\s\"']+", "Authorization: [REDACTED]", ...)
```

| Input fragment | After step 4 (old) | Leak |
|----------------|-------------------|------|
| `Authorization: Bearer X` | `Authorization: [REDACTED]` | — |
| `Authorization: Bearer TESTTOKEN` | `Authorization: [REDACTED] BEARER_LEAK_ME` if line also had `BEARER_LEAK_ME` | `BEARER_LEAK_ME` never matched any pattern |
| `api_key=LEAK_ME` | `api_key=[REDACTED]` | ✅ |
| `token=LEAK` | `token=[REDACTED]` | ✅ |

**Root causes:**

1. `Authorization:` pattern stopped at first whitespace — `Bearer TESTTOKEN` left orphan `TESTTOKEN` when Bearer sub-pattern ran separately on partial remainder.
2. Standalone canaries `BEARER_LEAK_ME`, `TOKEN_*` had no explicit patterns.
3. Order: generic `Authorization:` ran before full `Authorization: Bearer <token>` capture.

## 174F fix (`_redact_secret_values`)

**Order change — Bearer-first:**

```python
# Full Bearer forms before generic Authorization
Authorization\s*=\s*Bearer\s+[A-Za-z0-9._\-]+  → Authorization=Bearer [REDACTED]
Authorization:\s*Bearer\s+[A-Za-z0-9._\-]+   → Authorization: Bearer [REDACTED]
Bearer\s+[A-Za-z0-9._\-]+                     → Bearer [REDACTED]
```

**New canary patterns:**

```python
BEARER_[A-Za-z0-9_]+  → [REDACTED]
TOKEN_[A-Za-z0-9_]+    → [REDACTED]
LEAK_ME                → [REDACTED]
```

**Existing coverage retained:**

- `api_key=`, `API_KEY=`, `token=`, `access_token=`, `refresh_token=` (key=value)
- JSON `"access_token": "..."` 
- `sk-ant-*`, `ghp_*`, `eyJ*` JWT prefixes

## Post-fix launcher.log excerpt

```
Failure at [path-redacted] with [secret-redacted] and api_key=[REDACTED] and token=[REDACTED] and Authorization: Bearer [REDACTED] [REDACTED]
```

| Canary | Survives? |
|--------|-----------|
| Absolute path | ❌ `[path-redacted]` |
| `SECRET_X` | ❌ `[secret-redacted]` |
| `api_key=LEAK_ME` | ❌ |
| `token=LEAK` | ❌ |
| `Authorization: Bearer X` | ❌ |
| `BEARER_LEAK_ME` | ❌ |

## Requirement

No token-like values survive in support bundle logs or sanitized JSON payloads.
