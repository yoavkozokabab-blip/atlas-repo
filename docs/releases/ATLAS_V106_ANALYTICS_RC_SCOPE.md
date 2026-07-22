# Atlas v1.0.6 analytics-only RC scope

The release keeps account implementation in Git history but does not activate it.

Disabled account paths:

- Desktop account UI defaults to `local_only`; Sign In and Create Account remain hidden and disabled.
- `ATLAS_SUPABASE_AUTH_BRIDGE` is not enabled and its migration is not part of this release.
- The server-authoritative sessions migration is not part of this release.
- Account create, login, logout, deletion, and password-reset events are absent from the analytics contract.
- The local analytics pipeline does not invoke the legacy accounts telemetry/acquisition mirror.
- No production user row is read for analytics identity, changed, migrated, or deleted.
- The analytics-only migration does not reference `public.users`, `auth.users`, or account/session tables.
- Atlas local mode remains independent of account-service availability.

Release packaging must exclude `AtlasAccounts.exe`; its source and build definition remain for a later account release.
