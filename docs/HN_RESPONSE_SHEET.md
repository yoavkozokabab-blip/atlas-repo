# HN Response Sheet — 20 likely critical comments

Rules: concede real limitations in the first sentence. Point at /security#data-flow and the release SHA for trust claims. Never invent numbers.

1. **"Unsigned installer from an unknown dev? No thanks."**
   Fair. Signing is in progress (new-publisher identity verification takes time). SHA256 is on the release and the site; the source is publicly visible on GitHub if you want to read what you'd be running.

2. **"Why would I run a random .exe when I can write a CLAUDE.md?"**
   If a hand-maintained file works for your repo size, keep it. Atlas exists for the point where that file drifts: it validates a content signature and refuses to serve stale context instead of letting the agent read last month's map.

3. **"Cursor already indexes my codebase."**
   For Cursor, yes. Atlas is one index that Claude Code, Cursor, and Codex share, it persists across sessions with explicit staleness detection, and adds deterministic impact analysis. If you only use Cursor and its retrieval satisfies you, you don't need Atlas.

4. **"This is just Serena."**
   Closest neighbor, credit to them. Differences I'd defend: persisted validated scans that restore in fresh sessions, what-breaks analysis on the resolved import graph, and one-click multi-agent MCP setup with config backups. If Serena fits your workflow, use it.

5. **"'Ask Atlas' is just keyword routing, not AI."**
   Correct, and deliberate: deterministic lookups against the index cite real files and can't hallucinate. Your agent supplies the intelligence; Atlas supplies verified structure.

6. **"It uploaded my code somewhere, didn't it?"**
   No — there's no server to upload to; indexing has no network path. Watch it with a network monitor (genuinely, please do). Data-flow breakdown per stage: /security#data-flow. The only network path for your code remains your agent → its model provider.

7. **"Windows only? In 2026?"**
   Yes — one platform shipped well before three shipped badly. Core is portable Python; macOS/Linux are next on the roadmap.

8. **"Closed source but you want me to index my proprietary code with it."**
   Source-visible on GitHub (proprietary license). Read the indexing and MCP code before running it; the privacy claims are checkable against the code.

9. **"$19/month for grep with extra steps?"**
   The core app is free forever, no account. $19 is for future capacity features (sync, snapshots) and isn't even purchasable yet — checkout ships disabled until billing is verified.

10. **"Impact analysis can't possibly be sound."**
    It's sound only over statically resolved imports and says so — dynamic dispatch, reflection, and string imports are invisible. Every result cites its evidence so you can check it.

11. **"What happens when the index goes stale?"**
    Sorted content-hashed manifest signature; validated on every fresh session; stale → explicit refusal with the reason and a rescan prompt. Never silently served.

12. **"Your restore benchmark is a toy repo."**
    Correct — 27 files, controlled, one machine, and it's labeled that way. It demonstrates the restore path works without a graph rebuild, nothing more. Large-monorepo indexing is honestly slow today.

13. **"MCP tools that write my config files scare me."**
    Timestamped backup first, only the `atlas` entry merged, other servers preserved, output validated before an atomic replace, malformed configs refused with a paste-yourself snippet. Tested against empty/malformed/read-only configs and non-ASCII paths.

14. **"Python-only analysis, useless for my Go monorepo."**
    Deep graph analysis is Python + JS/TS today; Go/Rust/Java/C#/Ruby get file-level scanning, which is honestly weaker. If your stack is outside the deep set, Atlas gives you less — said plainly on the site.

15. **"How is this different from RAG over my repo?"**
    No embeddings, no vector DB, no model. It's a deterministic structural index (imports, symbols, subsystems) with citations — closer to a persistent ctags+graph than RAG, and it composes with whatever retrieval your agent does.

16. **"SmartScreen means malware."**
    SmartScreen means unsigned-new-publisher. Verify the SHA256 against the GitHub release; the first-launch screen explains the same thing in-app.

17. **"No telemetry, right?"** / **"What analytics?"**
    Local-only aggregate event names on desktop (scan succeeded, MCP connected). Website analytics is inert unless an endpoint env var is set, and sends event names + path only. Never code, prompts, or file paths. Privacy page matches the code.

18. **"Why does it run a local web server?"**
    The UI is a local browser app served on 127.0.0.1; MCP runs over stdio. Nothing binds beyond localhost.

19. **"What about repos with secrets in them?"**
    Indexing stores structure and capped content hashes locally; MCP responses and analytics run through a secret-redaction filter (sk-/ghp_/bearer/api_key patterns). Your secrets stay in your files on your disk — treat the data dir with the same care as the repo.

20. **"Solo dev — this will be abandoned in a month."**
    Real risk with any solo tool. Mitigations: local-first means the app keeps working without any service; your data is plain JSON on your disk; delete `~/.atlas_desktop` and it's gone. The launch plan and runbooks are in the repo — judge the seriousness from there.
