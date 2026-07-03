# GitHub "Make Public" Checklist

Run before flipping the repository to public.

## Must be present
```
[ ] README.md describes Atlas (not Atlas), with one-liner + GIF
[ ] LICENSE present and correct (proprietary vs OSS-core decided)
[ ] Screenshots of the evidence / context-pack output
[ ] Demo GIF (scan -> ask -> answer in <20s)
[ ] Quickstart (install -> connect -> first query)
[ ] Install guide (Windows; SmartScreen note)
[ ] MCP guide (README_MCP.md — 18 tools, generic paths)
[ ] examples/ (sample config + sample prompts)
[ ] SECURITY.md (private vuln reporting; links to docs/LOCAL_FIRST.md)
[ ] CONTRIBUTING.md
[ ] .github/ISSUE_TEMPLATE (bug, feature, feedback)
[ ] Release notes for v1.0.0
[ ] PRIVACY.md and TERMS.md reviewed by counsel
```

## Must NOT be public (exclude / scrub before going public)
```
[ ] .env / .env.local / any secret or JWT  (rotate anything ever committed)
[ ] data/            (runtime logs/state; observability_events.jsonl)
[ ] *.db             (test databases at repo root)
[ ] dist/ , packaging/installer/staging/ , installer/output/  (build artifacts)
[ ] reports/         (internal audits/benchmarks)
[ ] external_repos/  (third-party benchmark repos — never publish/ship)
[ ] internal docs not meant for users (audit/strategy notes)
[ ] the Atlas graveyard if it confuses (voice/ browser/ autonomy/ ...)
```

## Before publishing
```
[ ] git history scrubbed of any leaked secret
[ ] Support/contact email set and controlled (do NOT publish an uncontrolled address)
[ ] All [VERIFY] claims in PRIVACY.md / docs/LOCAL_FIRST.md confirmed
```
