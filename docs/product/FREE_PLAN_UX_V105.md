# Free Plan — User-Facing UX Contract (v1.0.5)

Copy and interaction contract only. Enforcement, entitlement storage, and limits
configuration are owned by Codex. Frontend must render whatever the entitlement
service reports; nothing here hardcodes a number.

## Policy assumed (confirm against Codex implementation before shipping)

- One active non-demo repository
- One connected MCP client
- Configurable advanced Impact allowance (daily)
- Demo repositories always usable, never counted against limits
- No multi-repository workspace, no team/shared context
- Pro is "coming soon" — **no payment action exists anywhere**

## Tone rules

Clear, neutral, non-punitive. No fake urgency, no countdown pressure, no broken or
disabled payment CTA styled as enabled, no implication payment is currently possible.
Every limit message states: what happened, when/how it resets or what to do instead,
and (optionally) that Pro is coming soon. Never blame the user.

## Canonical copy

| State | Copy |
|---|---|
| Primary Impact limit reached | "You've reached today's Free Impact limit. Your allowance resets at {time}. Pro is coming soon." |
| Quota remaining (meter label) | "{n} of {total} advanced Impact analyses left today" |
| Quota reset time (tooltip/subtext) | "Resets at {time} ({timezone})." |
| Repository limit reached | "Free includes one active repository. Unload the current repository to scan a different one — or keep using the demo, which is always available." |
| MCP client limit reached | "Free connects one MCP client at a time. Disconnect {client} to connect a different one." |
| Feature requires future Pro | "This will be part of Atlas Pro, which is coming soon. Nothing to buy yet." |
| Entitlement service temporarily unavailable | "Atlas can't check your plan limits right now. Core features keep working; limited features will retry automatically." |
| Offline grace expired | "Atlas needs to reach the entitlement service once to refresh your Free plan. Reconnect to the internet and Atlas will retry automatically." |
| Demo exemption (subtext wherever limits show) | "Demo repositories don't count toward Free limits." |
| Direct retry guidance (after transient failure) | "Try again — if this keeps happening, use Report a bug in the footer." |

## Interaction requirements

- Limit states are **inline panel states**, not blocking modals, and never global
  error banners.
- The meter is visible *before* the user hits the limit (no surprise walls).
- Reset time is shown in the user's local timezone, absolute ("resets at 09:00"),
  not a bare countdown.
- "Pro is coming soon" is plain text or a ghost chip — never a button that looks
  actionable, never a link to a checkout route.
- Accessibility: state changes announced via the existing `aria-live` regions;
  meaning never conveyed by color alone.
- Demo flows must never render a limit message.

## Explicitly forbidden

- "Upgrade now" buttons (there is nothing to upgrade to yet)
- Fake discounts, timers, or seat scarcity
- Punitive phrasing ("You have exceeded…", "Violation…")
- Disabling unrelated features when one quota is exhausted
