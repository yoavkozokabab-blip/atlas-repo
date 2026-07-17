# Analytics Disclosure & Opt-Out — User-Facing Contract (v1.0.5)

Copy and interaction requirements only. Collection, storage, and enforcement are
owned by Codex. **Gate:** verify this wording matches the actual implementation
(event list and payloads) before shipping; if implementation collects less, say
less — never more.

## What Atlas may collect (disclosure list)

- Anonymous website page/session metrics
- Active-time estimates (foreground/interaction time, not wall-clock)
- Download clicks
- First app run
- Screen usage (screen ids only)
- Workflow completion/failure (event names, durations, coarse buckets)
- App version
- Guest/account state category (guest vs signed-in — never identity)
- MCP client connected/disconnected events (client name only)

## What Atlas must never collect (hard list — mirrors the event contract)

Source code · repository names · repository paths · filenames · prompts · answers ·
graph contents · MCP payloads · secrets · command lines.

## Settings toggle

- **Label:** "Share anonymous usage analytics"
- **Description (under the toggle):** "Helps improve Atlas by sharing anonymous
  feature and performance events. Repository contents, paths, file names, prompts,
  and answers are never included."
- Toggle takes effect immediately; no restart. State persists per installation.

## First-run disclosure (onboarding step 2, one sentence + link)

"Atlas shares anonymous usage events to improve the product — never your code,
paths, prompts, or answers. You can turn this off anytime in Settings."
(Links to Settings and the Privacy page. If analytics ships default-off, swap to:
"Analytics is off by default. You can opt in from Settings.")

## Opt-out confirmation (inline, after toggling off)

"Anonymous analytics is off. Nothing is shared from this installation."
No guilt copy, no "are you sure?" modal.

## State copy

| State | Copy |
|---|---|
| Analytics unavailable (endpoint unreachable) | "Analytics is currently unavailable. This doesn't affect any Atlas features." |
| Analytics disabled (by toggle) | "Analytics is off. No usage events are shared from this installation." |

Neither state may render as an error banner or affect feature availability.

## Privacy page wording (drop-in paragraph)

"Atlas collects anonymous usage analytics to improve the product: feature events,
screen usage, timing, app version, and coarse categories such as guest vs
signed-in. Analytics never includes source code, repository names or paths, file
names, prompts, answers, graph contents, or MCP payloads. You can disable
analytics at any time in Settings → 'Share anonymous usage analytics'. Disabling
it does not change any functionality."

Note: if any persistent identifier (e.g., installation id) accompanies events, say
"anonymous" only if it cannot be tied to identity; otherwise use
"pseudonymous, per-installation" — do not claim "fully anonymous" with a
persistent identifier attached.
