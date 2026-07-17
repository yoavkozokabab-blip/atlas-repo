# Privacy & Security Copy Audit (v1.0.5)

Scope: all public claims on the website and in-app copy at integration commit
`526519c7`. No security implementation reviewed or changed — copy only.

## Verdict

**PASS with two precision corrections.** No absolute claims found: nothing claims
"completely secure", "impossible to hack", "military-grade", "guaranteed breakage
detection", or unqualified "fully anonymous". The privacy page correctly scopes the
no-upload claim to indexing, and the security page correctly discloses the local
data directory and deletion path.

## Verified-accurate claims (keep)

- "Repository indexing happens on your machine." (privacy, security, docs, FAQ)
- "Atlas does not upload repository contents **during indexing**." — correctly
  qualified, does not overreach into MCP flows.
- "Analytics: event names and basic metadata only; never repository contents,
  prompts, secrets, or raw file paths." (security page)
- Unsigned-installer + SmartScreen disclosure on /download and /hn.
- Windows-only disclosure in facts/hero/downloads.
- Benchmarks: "Numbers are self-measured on one Windows development machine; your
  hardware will differ." — appropriately hedged.
- Impact framed as "evidence-backed" with "may/likely" hedging (hero, Impact copy).

## Corrections for Codex to apply (exact)

1. **Add the MCP data-flow qualifier near the local-first claims.**
   Where: /privacy "local-first" section and /security indexing paragraph.
   Add sentence: "If you connect an external MCP client (Claude Code, Cursor,
   Codex), that client may send the context you request to its configured model
   provider. Atlas itself does not upload your repository."
   Why: "your code stays on your machine" is true of Atlas, but a first-time reader
   may extend it to the agent workflow; the qualifier keeps the claim precise.

2. **Analytics "anonymous" phrasing must match identifier reality.**
   If events carry a persistent installation id, use "pseudonymous, per-installation
   analytics (no identity, no code)" instead of bare "anonymous" on /privacy and in
   the Settings description. If no persistent identifier ships, "anonymous" stands.
   (See ANALYTICS_DISCLOSURE_AND_OPTOUT_V105.md.)

## Language to keep out (recurring-review list)

completely secure · impossible to · never leaves your machine (unqualified) ·
guaranteed detection · private by design (unqualified) · military-grade ·
fully anonymous (with persistent ids) · "the only tool that…"
