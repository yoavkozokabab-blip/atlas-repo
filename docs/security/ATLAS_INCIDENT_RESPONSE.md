# Atlas incident response

1. Preserve minimal evidence: affected release hash, installer SHA-256,
timestamps, relevant server audit IDs, and sanitized logs. Do not collect or
publish repository source.
2. Classify: secret exposure, account/session abuse, entitlement/billing error,
malicious dependency, compromised installer, or data exposure.
3. Contain: revoke release/download where necessary, rotate affected server
credentials, force logout/revoke sessions, freeze entitlements, and disable the
provider feature flag. Preserve Free access where safe.
4. Recover from a clean, provenance-recorded build; publish only a new verified
release, never replace an immutable asset silently.
5. Communicate scope, user action, remediation, and update path without
including secrets or private repository data.
