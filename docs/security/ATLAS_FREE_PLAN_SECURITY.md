# Atlas Free-plan security contract

## Initial policy

Free permits one active repository, basic Files/Memory/Graph/Ask/Debug/Plan,
the bundled demo, and a configurable number of advanced Impact analyses per
rolling window. It denies multi-repository workspaces, advanced exports,
background priority work, and more than one connected MCP client. Limits must
be server/config driven, never inferred from frontend state.

## Authority and failure modes

Authenticated entitlement and usage state is server-authoritative. The desktop
may cache an integrity-protected response for bounded offline use, but no cache
may grant Pro or extend an expired paid entitlement. A missing authority
preserves safe Free functionality and returns `ENTITLEMENT_UNAVAILABLE` for
features that require a fresh decision.

Safe client contract: `FREE_LIMIT_REACHED`, `REPOSITORY_LIMIT_REACHED`,
`FEATURE_REQUIRES_PRO`, `ENTITLEMENT_UNAVAILABLE`, and
`OFFLINE_GRACE_EXPIRED`. The payload includes only plan, feature, limit, used,
remaining, reset time, source, and last sync; it never contains billing secrets
or repository contents.

## Anti-bypass posture

Account quotas resist local file edits, reinstall, clock changes, forged UI
state, and duplicated installation IDs through server identity and atomic usage
metering. Guest/offline controls are intentionally privacy-preserving and can
only raise the cost of bypass; Atlas does not use hardware fingerprinting or
claim the Free tier is piracy-proof.
