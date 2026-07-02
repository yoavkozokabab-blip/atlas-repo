# 06 — First Value Moment QA

**Date:** 2026-06-20. Target moment: *"Use Atlas to scan this repo and tell me where authentication is implemented."*

| Question | Answer |
|---|---|
| Do docs tell them to ask this? | ✓ `docs/MCP_CLIENT_SETUP.md` §7 has example prompts ("Ask Atlas what files matter for…", "what breaks if I change…"). Close to the auth example; could add the literal auth phrasing. |
| Does the website tell them how to verify Atlas? | ✓ (added) download page: "Verify by asking *What Atlas tools are available?* / *Use atlas_health.*" |
| Does the desktop tell them how to verify? | Partial — diagnostics/support exist; the desktop doesn't explicitly say "ask Claude to use atlas_health". |
| Is there a sample repo? | ✓ a bundled demo repo + "Load Sample Repository" in the desktop GUI; the MCP path can scan any local repo. |
| Is there a demo question? | ✓ example prompts in docs; the download page gives the verify prompt. |
| Is the success state obvious? | ✓ "atlas" in the tools menu + a returned context pack (ranked files/symbols). Proven end-to-end by `mcp_install_proof.py` (atlas_scan_repo→125 files, atlas_repo_summary→requests). |

## Assessment
The first-value path is **achievable and documented** for a technical user: install → MCP config → restart Claude → ask. The **frozen-exe MCP handshake is proven** (report: install-MCP proof PASSED). The auth-finding query specifically maps to `atlas_build_context_pack`/`atlas_find_relevant_files`, which the engine handles well (retrieval benchmark: right files in top-3/5).

## Small gap (docs only)
The example prompts don't include the exact "where is authentication implemented?" phrasing the user will likely try first. A one-line addition to `docs/MCP_CLIENT_SETUP.md` examples would tighten the first-value moment. (Left as a P1 doc tweak; the existing examples already cover the pattern.)
