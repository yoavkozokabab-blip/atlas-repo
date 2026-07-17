# Final Screenshot Manifest — v1.0.5 (installed candidate)

Global rules — every shot: neutral Windows accent (no pink/red title bar), demo
content only, footer "Atlas 1.0.5", no private paths, no full hashes, no emails,
no QA/test wording, no error toasts unless the state *is* the subject.
Desktop viewport: **1440×900**. Website: 1440×900 desktop / 375×812 mobile.

## Desktop (16)

| Shot | State to stage | Reject if |
|---|---|---|
| onboarding step 1 | Fresh profile, tour open, step 1/4 | Progress dots missing; text clipped |
| onboarding demo step | Step 3 "Load a repository" | Demo button not primary |
| Home | Medium demo loaded, memory current | "Analyze impact" not the primary CTA; stale repo name |
| Memory | Demo loaded, memory restored | Empty panels |
| Files | Demo loaded, 17 indexed listed | Empty list |
| Graph | Subsystem view rendered | Blank canvas / loading spinner |
| Ask completed | The subsystems question answered | Empty answer with success framing |
| Impact completed | `services/billing.py`, 8 dependents visible | Empty result panel; missing risk/confidence |
| Impact target not found | `no/such_file.py` | Generic error panel instead of the distinct state |
| Debug completed | Billing symptom, hypotheses visible | Placeholder text visible |
| Plan completed | Retry-logic brief, ordered files visible | Empty tiers |
| Agents all disconnected | No client connected | Any "Connected" badge; false state |
| Agents Cursor connected | After real Cursor handshake | "Connected" without live connection (verify against Cursor actually running) |
| Settings analytics opt-out | Toggle + description visible | Wording differs from disclosure doc |
| Free-limit state | Impact allowance exhausted (test config) | Punitive copy; payment button |
| Repository selector | Selector open over Home | Private repo names in recents |

## Website (10)

| Shot | Viewport | Reject if |
|---|---|---|
| homepage desktop | 1440×900 | Hero clipped; footer version ≠ served release |
| homepage mobile | 375×812 | Horizontal overflow; CTA below fold entirely |
| features | 1440×900 | Overclaim copy |
| how it works | 1440×900 | Stale flow description |
| integrations | 1440×900 | "Connected" claims for unverified clients |
| download | 1440×900 | Missing SHA-256 or SmartScreen note; wrong release version |
| pricing | 1440×900 | Anything implying live checkout |
| security | 1440×900 | Absolute security claims |
| privacy | 1440×900 | Missing MCP data-flow qualifier (after Codex applies it) |
| HN page | 1440×900 | Stale benchmarks label; missing disclosures |
